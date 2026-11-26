from sqlalchemy.orm import Session, joinedload

from app.models.domain import (
    Course,
    CoursePrerequisite,
    Registration,
    RegistrationItem,
    Semester,
    StudentCompletedCourse,
    StudentProfile,
    User,
)


class RegistrationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_user_by_email(self, email: str) -> User | None:
        return self.db.query(User).filter(User.email == email.lower().strip()).first()

    def get_user_by_id(self, user_id: str) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()

    def get_active_semester(self) -> Semester | None:
        return self.db.query(Semester).first()

    def list_courses(
        self, semester_id: str, level: int | None = None, query: str | None = None
    ) -> list[Course]:
        q = (
            self.db.query(Course)
            .options(joinedload(Course.prerequisites))
            .filter(Course.semester_id == semester_id)
        )
        if level:
            q = q.filter(Course.level == level)
        if query:
            like = f"%{query.strip()}%"
            q = q.filter((Course.code.ilike(like)) | (Course.title.ilike(like)))
        return q.order_by(Course.level.asc(), Course.code.asc()).all()

    def get_course_by_id(self, course_id: str) -> Course | None:
        return (
            self.db.query(Course)
            .options(joinedload(Course.prerequisites))
            .filter(Course.id == course_id)
            .first()
        )

    def create_course(
        self, semester_id: str, data: dict, prereq_codes: list[str]
    ) -> Course:
        course = Course(semester_id=semester_id, **data)
        self.db.add(course)
        self.db.flush()
        for code in prereq_codes:
            clean = code.strip().upper()
            if clean:
                self.db.add(
                    CoursePrerequisite(course_id=course.id, prerequisite_code=clean)
                )
        self.db.commit()
        self.db.refresh(course)
        return course

    def get_passed_course_codes(self, student_id: str) -> set[str]:
        rows = (
            self.db.query(StudentCompletedCourse.course_code)
            .filter(StudentCompletedCourse.student_id == student_id)
            .all()
        )
        return {r[0] for r in rows}

    def get_or_create_registration(
        self, student_id: str, semester_id: str
    ) -> Registration:
        reg = (
            self.db.query(Registration)
            .options(
                joinedload(Registration.items)
                .joinedload(RegistrationItem.course)
                .joinedload(Course.prerequisites)
            )
            .filter(
                Registration.student_id == student_id,
                Registration.semester_id == semester_id,
            )
            .first()
        )
        if not reg:
            reg = Registration(
                student_id=student_id,
                semester_id=semester_id,
                status="DRAFT",
                total_credits=0,
            )
            self.db.add(reg)
            self.db.commit()
            self.db.refresh(reg)
        return reg

    def get_registration_by_id(self, reg_id: str) -> Registration | None:
        return (
            self.db.query(Registration)
            .options(
                joinedload(Registration.items)
                .joinedload(RegistrationItem.course)
                .joinedload(Course.prerequisites),
                joinedload(Registration.student).joinedload(User.student_profile),
                joinedload(Registration.semester),
            )
            .filter(Registration.id == reg_id)
            .first()
        )

    def list_advisee_registrations(
        self, advisor_id: str, semester_id: str
    ) -> list[Registration]:
        student_ids = [
            r[0]
            for r in self.db.query(StudentProfile.user_id)
            .filter(StudentProfile.advisor_id == advisor_id)
            .all()
        ]
        if not student_ids:
            return []
        return (
            self.db.query(Registration)
            .options(
                joinedload(Registration.items)
                .joinedload(RegistrationItem.course)
                .joinedload(Course.prerequisites),
                joinedload(Registration.student).joinedload(User.student_profile),
                joinedload(Registration.semester),
            )
            .filter(
                Registration.student_id.in_(student_ids),
                Registration.semester_id == semester_id,
            )
            .all()
        )
