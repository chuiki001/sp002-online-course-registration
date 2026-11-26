from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.domain import (
    Course,
    CoursePrerequisite,
    Semester,
    StudentCompletedCourse,
    StudentProfile,
    User,
)


def seed_initial_data(db: Session) -> None:
    if db.query(User).first():
        return

    # 1. Users: Admin, Advisor, 2 Students
    admin = User(
        full_name="Prof. Ibrahim Danjuma",
        email="admin@afit.edu.ng",
        password_hash=hash_password("admin123"),
        role="ADMIN",
    )
    advisor = User(
        full_name="Dr. Amina Musa",
        email="advisor@afit.edu.ng",
        password_hash=hash_password("advisor123"),
        role="ADVISOR",
    )
    student1 = User(
        full_name="Chika Praise Palngnen",
        email="u23cs1038@afit.edu.ng",
        password_hash=hash_password("student123"),
        role="STUDENT",
    )
    student2 = User(
        full_name="Tunde Adeyemi",
        email="u23cs1019@afit.edu.ng",
        password_hash=hash_password("student123"),
        role="STUDENT",
    )
    db.add_all([admin, advisor, student1, student2])
    db.flush()

    db.add_all(
        [
            StudentProfile(
                user_id=student1.id,
                matric_number="U23CS1038",
                department="Computer Science",
                level=400,
                advisor_id=advisor.id,
            ),
            StudentProfile(
                user_id=student2.id,
                matric_number="U23CS1019",
                department="Computer Science",
                level=400,
                advisor_id=advisor.id,
            ),
        ]
    )

    # 2. Active Semester
    sem = Semester(code="2026/2027-SEM1", status="OPEN", min_credits=15, max_credits=24)
    db.add(sem)
    db.flush()

    # 3. Courses (Designed to demonstrate prerequisites, timetable clashes, and credit limits!)
    courses_data = [
        # Valid 400L Core Courses (Total = 18 CU if all 6 selected, zero clashes!)
        {
            "code": "CSC401",
            "title": "Software Engineering & Architecture",
            "credit_units": 3,
            "level": 400,
            "capacity": 60,
            "enrolled_count": 18,
            "day_of_week": "MON",
            "start_time": "08:00",
            "end_time": "10:00",
            "prereqs": ["CSC301"],
        },
        {
            "code": "CSC403",
            "title": "Computer & Network Security",
            "credit_units": 3,
            "level": 400,
            "capacity": 50,
            "enrolled_count": 22,
            "day_of_week": "TUE",
            "start_time": "10:00",
            "end_time": "12:00",
            "prereqs": ["CSC305"],
        },
        {
            "code": "CSC405",
            "title": "Artificial Intelligence & Machine Learning",
            "credit_units": 3,
            "level": 400,
            "capacity": 55,
            "enrolled_count": 31,
            "day_of_week": "WED",
            "start_time": "08:00",
            "end_time": "10:00",
            "prereqs": ["CSC303"],
        },
        {
            "code": "CSC407",
            "title": "Database Management & Distributed Systems",
            "credit_units": 3,
            "level": 400,
            "capacity": 60,
            "enrolled_count": 27,
            "day_of_week": "THU",
            "start_time": "12:00",
            "end_time": "14:00",
            "prereqs": ["CSC307"],
        },
        {
            "code": "CSC409",
            "title": "Operating Systems & Concurrency",
            "credit_units": 3,
            "level": 400,
            "capacity": 50,
            "enrolled_count": 19,
            "day_of_week": "FRI",
            "start_time": "09:00",
            "end_time": "11:00",
            "prereqs": [],
        },
        {
            "code": "CSC411",
            "title": "Human-Computer Interaction & UI Design",
            "credit_units": 3,
            "level": 400,
            "capacity": 45,
            "enrolled_count": 14,
            "day_of_week": "TUE",
            "start_time": "14:00",
            "end_time": "16:00",
            "prereqs": [],
        },
        # Deliberate Edge-Case Courses for Live Demo:
        # (a) Timetable Clash with CSC401 (MON 09:00-11:00 overlaps MON 08:00-10:00)
        {
            "code": "CSC413",
            "title": "Compiler Construction (Clashes w/ CSC401)",
            "credit_units": 3,
            "level": 400,
            "capacity": 40,
            "enrolled_count": 10,
            "day_of_week": "MON",
            "start_time": "09:00",
            "end_time": "11:00",
            "prereqs": [],
        },
        # (b) Unmet Prerequisite (Requires CSC399 which student has NOT passed)
        {
            "code": "CSC415",
            "title": "Quantum Computing Seminar (Requires CSC399)",
            "credit_units": 3,
            "level": 400,
            "capacity": 30,
            "enrolled_count": 5,
            "day_of_week": "THU",
            "start_time": "15:00",
            "end_time": "17:00",
            "prereqs": ["CSC399"],
        },
        # (c) Full Capacity Course (30/30 seats taken)
        {
            "code": "CSC417",
            "title": "Cloud Native DevOps (Full Quota)",
            "credit_units": 3,
            "level": 400,
            "capacity": 30,
            "enrolled_count": 30,
            "day_of_week": "WED",
            "start_time": "14:00",
            "end_time": "16:00",
            "prereqs": [],
        },
        # (d) 300L Carryover / Elective Option
        {
            "code": "CSC309",
            "title": "Web Technologies & REST APIs",
            "credit_units": 3,
            "level": 300,
            "capacity": 70,
            "enrolled_count": 41,
            "day_of_week": "FRI",
            "start_time": "14:00",
            "end_time": "16:00",
            "prereqs": [],
        },
    ]

    for item in courses_data:
        prereqs = item.pop("prereqs")
        c = Course(semester_id=sem.id, **item)
        db.add(c)
        db.flush()
        for p in prereqs:
            db.add(CoursePrerequisite(course_id=c.id, prerequisite_code=p))

    # 4. Passed 300L Courses for both students
    passed = [("CSC301", "A"), ("CSC303", "A"), ("CSC305", "B"), ("CSC307", "A")]
    for sid in (student1.id, student2.id):
        for code, grade in passed:
            db.add(
                StudentCompletedCourse(student_id=sid, course_code=code, grade=grade)
            )

    db.commit()
