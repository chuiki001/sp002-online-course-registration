import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    full_name = Column(String(120), nullable=False)
    email = Column(String(150), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)  # STUDENT | ADVISOR | ADMIN
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    student_profile = relationship(
        "StudentProfile",
        back_populates="user",
        uselist=False,
        foreign_keys="StudentProfile.user_id",
        cascade="all, delete-orphan",
    )


class StudentProfile(Base):
    __tablename__ = "student_profiles"

    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    matric_number = Column(String(30), unique=True, nullable=False, index=True)
    department = Column(String(100), nullable=False)
    level = Column(Integer, nullable=False)
    advisor_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    user = relationship("User", back_populates="student_profile", foreign_keys=[user_id])
    advisor = relationship("User", foreign_keys=[advisor_id])


class Semester(Base):
    __tablename__ = "semesters"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    code = Column(String(30), unique=True, nullable=False)
    status = Column(String(20), nullable=False, default="OPEN")  # OPEN | ADD_DROP | CLOSED
    min_credits = Column(Integer, nullable=False, default=15)
    max_credits = Column(Integer, nullable=False, default=24)


class Course(Base):
    __tablename__ = "courses"
    __table_args__ = (UniqueConstraint("semester_id", "code", name="uq_semester_course_code"),)

    id = Column(String(36), primary_key=True, default=gen_uuid)
    semester_id = Column(String(36), ForeignKey("semesters.id", ondelete="CASCADE"), nullable=False)
    code = Column(String(15), nullable=False)
    title = Column(String(150), nullable=False)
    credit_units = Column(Integer, nullable=False)
    level = Column(Integer, nullable=False)
    capacity = Column(Integer, nullable=False)
    enrolled_count = Column(Integer, nullable=False, default=0)
    day_of_week = Column(String(10), nullable=False)  # MON..SAT
    start_time = Column(String(5), nullable=False)    # HH:MM
    end_time = Column(String(5), nullable=False)      # HH:MM

    prerequisites = relationship("CoursePrerequisite", back_populates="course", cascade="all, delete-orphan")


class CoursePrerequisite(Base):
    __tablename__ = "course_prerequisites"

    course_id = Column(String(36), ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True)
    prerequisite_code = Column(String(15), primary_key=True)

    course = relationship("Course", back_populates="prerequisites")


class StudentCompletedCourse(Base):
    __tablename__ = "student_completed_courses"

    student_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    course_code = Column(String(15), primary_key=True)
    grade = Column(String(2), nullable=False)


class Registration(Base):
    __tablename__ = "registrations"
    __table_args__ = (UniqueConstraint("student_id", "semester_id", name="uq_student_semester_reg"),)

    id = Column(String(36), primary_key=True, default=gen_uuid)
    student_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    semester_id = Column(String(36), ForeignKey("semesters.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), nullable=False, default="DRAFT")  # DRAFT | SUBMITTED | APPROVED | REJECTED
    total_credits = Column(Integer, nullable=False, default=0)
    advisor_remark = Column(Text, nullable=True)
    submitted_at = Column(DateTime, nullable=True)

    items = relationship("RegistrationItem", back_populates="registration", cascade="all, delete-orphan")
    student = relationship("User", foreign_keys=[student_id])
    semester = relationship("Semester", foreign_keys=[semester_id])


class RegistrationItem(Base):
    __tablename__ = "registration_items"
    __table_args__ = (UniqueConstraint("registration_id", "course_id", name="uq_reg_course"),)

    id = Column(String(36), primary_key=True, default=gen_uuid)
    registration_id = Column(String(36), ForeignKey("registrations.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(String(36), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    is_carryover = Column(Integer, nullable=False, default=0)  # CR-01 enhancement
    added_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    registration = relationship("Registration", back_populates="items")
    course = relationship("Course")
