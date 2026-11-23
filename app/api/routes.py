from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from app.api.deps import get_current_user, get_repo, require_role
from app.core.security import create_access_token, verify_password
from app.models.domain import Course, Registration, User
from app.repositories.registration_repo import RegistrationRepository
from app.schemas.dto import (
    AddCourseRequest,
    AdvisorDecisionRequest,
    CourseCreate,
    CourseOut,
    DashboardStatsOut,
    LoginRequest,
    RegistrationOut,
    SemesterOut,
    SemesterStatusUpdate,
    TokenResponse,
)
from app.services.portal_service import PortalService, serialize_course

router = APIRouter()


@router.post("/auth/login", response_model=TokenResponse, tags=["Authentication"])
def login(payload: LoginRequest, repo: RegistrationRepository = Depends(get_repo)):
    user = repo.get_user_by_email(payload.email)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")

    token = create_access_token(subject=user.id, role=user.role)
    profile = user.student_profile
    return TokenResponse(
        access_token=token,
        role=user.role,
        full_name=user.full_name,
        user_id=user.id,
        matric_number=profile.matric_number if profile else None,
        department=profile.department if profile else None,
        level=profile.level if profile else None,
    )


@router.get("/semester/active", response_model=SemesterOut, tags=["Catalog"])
def get_active_semester(repo: RegistrationRepository = Depends(get_repo)):
    sem = repo.get_active_semester()
    if not sem:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active semester configured.")
    return sem


@router.patch("/admin/semester/status", response_model=SemesterOut, tags=["Admin"])
def update_semester_status(
    payload: SemesterStatusUpdate,
    _: User = Depends(require_role("ADMIN")),
    repo: RegistrationRepository = Depends(get_repo),
):
    sem = repo.get_active_semester()
    if not sem:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active semester.")
    sem.status = payload.status
    repo.db.commit()
    repo.db.refresh(sem)
    return sem


@router.get("/courses", response_model=List[CourseOut], tags=["Catalog"])
def list_courses(
    level: Optional[int] = None,
    q: Optional[str] = None,
    repo: RegistrationRepository = Depends(get_repo),
):
    sem = repo.get_active_semester()
    if not sem:
        return []
    courses = repo.list_courses(semester_id=sem.id, level=level, query=q)
    return [serialize_course(c) for c in courses]


@router.post("/admin/courses", response_model=CourseOut, status_code=status.HTTP_201_CREATED, tags=["Admin"])
def create_course(
    payload: CourseCreate,
    _: User = Depends(require_role("ADMIN")),
    repo: RegistrationRepository = Depends(get_repo),
):
    sem = repo.get_active_semester()
    if not sem:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active semester.")
    if payload.end_time <= payload.start_time:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="end_time must be after start_time.")

    existing = [c for c in repo.list_courses(sem.id) if c.code.upper() == payload.code.upper()]
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Course {payload.code.upper()} already exists.")

    data = payload.model_dump(exclude={"prerequisites"})
    data["code"] = data["code"].upper().strip()
    course = repo.create_course(semester_id=sem.id, data=data, prereq_codes=payload.prerequisites)
    return serialize_course(course)


@router.get("/admin/analytics", response_model=DashboardStatsOut, tags=["Admin"])
def get_admin_analytics(
    _: User = Depends(require_role("ADMIN")),
    repo: RegistrationRepository = Depends(get_repo),
):
    sem = repo.get_active_semester()
    courses = repo.list_courses(sem.id) if sem else []
    total_seats = sum(c.capacity for c in courses)
    total_enrolled = sum(c.enrolled_count for c in courses)
    utilization = round((total_enrolled / total_seats * 100.0), 1) if total_seats else 0.0

    regs = repo.db.query(Registration).all()
    by_status = {"DRAFT": 0, "SUBMITTED": 0, "APPROVED": 0, "REJECTED": 0}
    for r in regs:
        by_status[r.status] = by_status.get(r.status, 0) + 1

    return DashboardStatsOut(
        total_courses=len(courses),
        total_seats=total_seats,
        total_enrolled=total_enrolled,
        utilization_pct=utilization,
        registrations_by_status=by_status,
    )


@router.get("/registrations/me", response_model=RegistrationOut, tags=["Student Registration"])
def get_my_registration(
    current_user: User = Depends(require_role("STUDENT")),
    repo: RegistrationRepository = Depends(get_repo),
):
    sem = repo.get_active_semester()
    if not sem:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active semester.")
    reg = repo.get_or_create_registration(current_user.id, sem.id)
    refreshed = repo.get_registration_by_id(reg.id)
    service = PortalService(repo)
    return service.build_registration_out(refreshed)


@router.post("/registrations/me/items", response_model=RegistrationOut, tags=["Student Registration"])
def add_course_to_my_cart(
    payload: AddCourseRequest,
    current_user: User = Depends(require_role("STUDENT")),
    repo: RegistrationRepository = Depends(get_repo),
):
    service = PortalService(repo)
    return service.add_course_to_cart(current_user.id, payload.course_id, payload.is_carryover)


@router.delete("/registrations/me/items/{course_id}", response_model=RegistrationOut, tags=["Student Registration"])
def remove_course_from_my_cart(
    course_id: str,
    current_user: User = Depends(require_role("STUDENT")),
    repo: RegistrationRepository = Depends(get_repo),
):
    service = PortalService(repo)
    return service.remove_course_from_cart(current_user.id, course_id)


@router.post("/registrations/me/submit", response_model=RegistrationOut, tags=["Student Registration"])
def submit_my_registration(
    current_user: User = Depends(require_role("STUDENT")),
    repo: RegistrationRepository = Depends(get_repo),
):
    service = PortalService(repo)
    return service.submit_registration(current_user.id)


@router.get("/advisor/submissions", response_model=List[RegistrationOut], tags=["Advisor Review"])
def get_advisee_submissions(
    current_user: User = Depends(require_role("ADVISOR")),
    repo: RegistrationRepository = Depends(get_repo),
):
    sem = repo.get_active_semester()
    if not sem:
        return []
    regs = repo.list_advisee_registrations(current_user.id, sem.id)
    service = PortalService(repo)
    return [service.build_registration_out(r) for r in regs]


@router.post("/advisor/submissions/{reg_id}/decision", response_model=RegistrationOut, tags=["Advisor Review"])
def review_advisee_submission(
    reg_id: str,
    payload: AdvisorDecisionRequest,
    current_user: User = Depends(require_role("ADVISOR")),
    repo: RegistrationRepository = Depends(get_repo),
):
    service = PortalService(repo)
    return service.process_advisor_decision(current_user.id, reg_id, payload.decision, payload.remark or "")
