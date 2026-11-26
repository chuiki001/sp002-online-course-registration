from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=4)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    full_name: str
    user_id: str
    matric_number: str | None = None
    department: str | None = None
    level: int | None = None


class SemesterOut(BaseModel):
    id: str
    code: str
    status: str
    min_credits: int
    max_credits: int

    class Config:
        from_attributes = True


class SemesterStatusUpdate(BaseModel):
    status: Literal["OPEN", "ADD_DROP", "CLOSED"]


class CourseCreate(BaseModel):
    code: str = Field(..., min_length=3, max_length=15)
    title: str = Field(..., min_length=3, max_length=150)
    credit_units: int = Field(..., ge=1, le=6)
    level: int = Field(..., ge=100, le=500)
    capacity: int = Field(..., ge=1, le=500)
    day_of_week: Literal["MON", "TUE", "WED", "THU", "FRI", "SAT"]
    start_time: str = Field(..., pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    end_time: str = Field(..., pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    prerequisites: list[str] = Field(default_factory=list)


class CourseOut(BaseModel):
    id: str
    semester_id: str
    code: str
    title: str
    credit_units: int
    level: int
    capacity: int
    enrolled_count: int
    available_seats: int
    day_of_week: str
    start_time: str
    end_time: str
    prerequisites: list[str]


class AddCourseRequest(BaseModel):
    course_id: str
    is_carryover: bool = False


class RegistrationItemOut(BaseModel):
    item_id: str
    course_id: str
    code: str
    title: str
    credit_units: int
    day_of_week: str
    start_time: str
    end_time: str
    is_carryover: bool


class RegistrationOut(BaseModel):
    id: str
    student_id: str
    student_name: str
    matric_number: str
    department: str
    level: int
    semester_code: str
    status: str
    total_credits: int
    min_credits: int
    max_credits: int
    advisor_remark: str | None = None
    submitted_at: datetime | None = None
    items: list[RegistrationItemOut]
    validation_errors: list[str]


class AdvisorDecisionRequest(BaseModel):
    decision: Literal["APPROVED", "REJECTED"]
    remark: str | None = ""


class DashboardStatsOut(BaseModel):
    total_courses: int
    total_seats: int
    total_enrolled: int
    utilization_pct: float
    registrations_by_status: dict[str, int]
