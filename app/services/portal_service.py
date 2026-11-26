from datetime import UTC, datetime

from fastapi import HTTPException, status

from app.core.validators import (
    CourseSlot,
    ValidationContext,
    build_default_validator,
)
from app.models.domain import Course, Registration, RegistrationItem, Semester, User
from app.repositories.registration_repo import RegistrationRepository
from app.schemas.dto import CourseOut, RegistrationItemOut, RegistrationOut


def _to_minutes(hhmm: str) -> int:
    h, m = map(int, hhmm.split(":"))
    return h * 60 + m


def course_to_slot(course: Course, is_carryover: bool = False) -> CourseSlot:
    return CourseSlot(
        code=course.code,
        credit_units=course.credit_units,
        day_of_week=course.day_of_week,
        start_minutes=_to_minutes(course.start_time),
        end_minutes=_to_minutes(course.end_time),
        capacity=course.capacity,
        enrolled_count=course.enrolled_count,
        prerequisites=tuple(p.prerequisite_code for p in course.prerequisites),
        is_carryover=is_carryover,
    )


def serialize_course(course: Course) -> CourseOut:
    return CourseOut(
        id=course.id,
        semester_id=course.semester_id,
        code=course.code,
        title=course.title,
        credit_units=course.credit_units,
        level=course.level,
        capacity=course.capacity,
        enrolled_count=course.enrolled_count,
        available_seats=max(0, course.capacity - course.enrolled_count),
        day_of_week=course.day_of_week,
        start_time=course.start_time,
        end_time=course.end_time,
        prerequisites=[p.prerequisite_code for p in course.prerequisites],
    )


class PortalService:
    def __init__(self, repo: RegistrationRepository) -> None:
        self.repo = repo

    def build_registration_out(self, reg: Registration) -> RegistrationOut:
        student: User = reg.student or self.repo.get_user_by_id(reg.student_id)
        profile = student.student_profile
        semester: Semester = reg.semester or self.repo.get_active_semester()
        passed_codes = self.repo.get_passed_course_codes(reg.student_id)

        slots = [
            course_to_slot(item.course, bool(item.is_carryover)) for item in reg.items
        ]
        ctx = ValidationContext(
            selected_courses=slots,
            passed_course_codes=passed_codes,
            min_credits=semester.min_credits,
            max_credits=semester.max_credits,
            allow_late_add_drop=(semester.status == "ADD_DROP"),
        )
        validator = build_default_validator(enforce_credit_bounds=True)
        errors = validator.validate_all(ctx)

        items_out = [
            RegistrationItemOut(
                item_id=item.id,
                course_id=item.course.id,
                code=item.course.code,
                title=item.course.title,
                credit_units=item.course.credit_units,
                day_of_week=item.course.day_of_week,
                start_time=item.course.start_time,
                end_time=item.course.end_time,
                is_carryover=bool(item.is_carryover),
            )
            for item in reg.items
        ]
        total_credits = sum(i.credit_units for i in items_out)

        return RegistrationOut(
            id=reg.id,
            student_id=reg.student_id,
            student_name=student.full_name,
            matric_number=profile.matric_number if profile else "N/A",
            department=profile.department if profile else "Computer Science",
            level=profile.level if profile else 400,
            semester_code=semester.code,
            status=reg.status,
            total_credits=total_credits,
            min_credits=semester.min_credits,
            max_credits=semester.max_credits,
            advisor_remark=reg.advisor_remark,
            submitted_at=reg.submitted_at,
            items=items_out,
            validation_errors=errors,
        )

    def add_course_to_cart(
        self, student_id: str, course_id: str, is_carryover: bool = False
    ) -> RegistrationOut:
        semester = self.repo.get_active_semester()
        if not semester or semester.status == "CLOSED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Registration window is currently closed.",
            )

        reg = self.repo.get_or_create_registration(student_id, semester.id)
        if reg.status == "APPROVED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Approved registration slips are locked.",
            )
        if reg.status == "SUBMITTED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Withdraw or await advisor review before editing.",
            )

        course = self.repo.get_course_by_id(course_id)
        if not course or course.semester_id != semester.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course not found in active semester.",
            )

        if any(item.course_id == course.id for item in reg.items):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"{course.code} is already in your registration cart.",
            )

        # Validate incremental constraints (Prerequisites, Clash, Seat Capacity, Upper Credit Bound)
        passed_codes = self.repo.get_passed_course_codes(student_id)
        candidate_slots = [
            course_to_slot(i.course, bool(i.is_carryover)) for i in reg.items
        ] + [course_to_slot(course, is_carryover)]
        ctx = ValidationContext(
            selected_courses=candidate_slots,
            passed_course_codes=passed_codes,
            min_credits=semester.min_credits,
            max_credits=semester.max_credits,
        )
        # Skip min_credits check while still adding courses to cart, enforce max_credits + rules
        validator = build_default_validator(enforce_credit_bounds=False)
        violations = validator.validate_all(ctx)
        projected_total = sum(s.credit_units for s in candidate_slots)
        if projected_total > semester.max_credits:
            violations.append(
                f"Adding {course.code} brings total to {projected_total} CU (max {semester.max_credits} CU)."
            )

        if violations:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="; ".join(violations),
            )

        item = RegistrationItem(
            registration_id=reg.id,
            course_id=course.id,
            is_carryover=1 if is_carryover else 0,
        )
        self.repo.db.add(item)
        reg.total_credits = projected_total
        if reg.status == "REJECTED":
            reg.status = "DRAFT"
        self.repo.db.commit()
        refreshed = self.repo.get_registration_by_id(reg.id)
        return self.build_registration_out(refreshed)

    def remove_course_from_cart(
        self, student_id: str, course_id: str
    ) -> RegistrationOut:
        semester = self.repo.get_active_semester()
        if not semester or semester.status == "CLOSED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Registration window is currently closed.",
            )

        reg = self.repo.get_or_create_registration(student_id, semester.id)
        if reg.status in ("APPROVED", "SUBMITTED"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot modify slip in {reg.status} status.",
            )

        target = next((i for i in reg.items if i.course_id == course_id), None)
        if not target:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course not in registration cart.",
            )

        self.repo.db.delete(target)
        self.repo.db.flush()
        refreshed = self.repo.get_registration_by_id(reg.id)
        refreshed.total_credits = sum(i.course.credit_units for i in refreshed.items)
        self.repo.db.commit()
        return self.build_registration_out(refreshed)

    def submit_registration(self, student_id: str) -> RegistrationOut:
        semester = self.repo.get_active_semester()
        if not semester or semester.status == "CLOSED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Registration window is closed.",
            )

        reg = self.repo.get_or_create_registration(student_id, semester.id)
        if reg.status in ("SUBMITTED", "APPROVED"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Slip is already {reg.status}.",
            )

        out = self.build_registration_out(reg)
        if out.validation_errors:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="; ".join(out.validation_errors),
            )

        # Reserve seats atomically
        for item in reg.items:
            if item.course.enrolled_count >= item.course.capacity:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Seat quota exhausted for {item.course.code}.",
                )
            item.course.enrolled_count += 1

        reg.status = "SUBMITTED"
        reg.total_credits = out.total_credits
        reg.submitted_at = datetime.now(UTC)
        reg.advisor_remark = None
        self.repo.db.commit()
        return self.build_registration_out(self.repo.get_registration_by_id(reg.id))

    def process_advisor_decision(
        self, advisor_id: str, reg_id: str, decision: str, remark: str
    ) -> RegistrationOut:
        reg = self.repo.get_registration_by_id(reg_id)
        if not reg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Registration slip not found.",
            )
        profile = reg.student.student_profile
        if not profile or profile.advisor_id != advisor_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not assigned as this student's advisor.",
            )
        if reg.status != "SUBMITTED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only SUBMITTED slips can be reviewed.",
            )

        if decision == "REJECTED":
            if not remark or not remark.strip():
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="A rejection remark is mandatory.",
                )
            # Release reserved seats so student can adjust
            for item in reg.items:
                item.course.enrolled_count = max(0, item.course.enrolled_count - 1)
            reg.status = "REJECTED"
            reg.advisor_remark = remark.strip()
        else:
            reg.status = "APPROVED"
            reg.advisor_remark = (
                remark.strip() if remark else "Approved by Academic Advisor."
            )

        self.repo.db.commit()
        return self.build_registration_out(self.repo.get_registration_by_id(reg.id))
