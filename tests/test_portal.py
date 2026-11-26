import os

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_sp002.db"

from app.core.database import Base, SessionLocal, engine
from app.core.validators import (
    CourseSlot,
    CreditLimitRule,
    PrerequisiteRule,
    SeatCapacityRule,
    TimetableClashRule,
    ValidationContext,
)
from app.main import app
from app.seed import seed_initial_data


@pytest.fixture(scope="module")
def client():
    if os.path.exists("test_sp002.db"):
        os.remove("test_sp002.db")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    seed_initial_data(db)
    db.close()
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("test_sp002.db"):
        os.remove("test_sp002.db")


# ==================== UNIT TESTS: SOLID VALIDATION ENGINE ====================
def test_credit_limit_rule_bounds():
    slot = CourseSlot("CSC401", 3, "MON", 480, 600, 50, 10, ())
    rule = CreditLimitRule()
    assert len(rule.validate(ValidationContext([slot], set(), 15, 24))) == 1
    assert len(rule.validate(ValidationContext([slot] * 6, set(), 15, 24))) == 0
    assert len(rule.validate(ValidationContext([slot] * 9, set(), 15, 24))) == 1


def test_prerequisite_rule_enforcement():
    slot = CourseSlot("CSC401", 3, "MON", 480, 600, 50, 10, ("CSC301",))
    rule = PrerequisiteRule()
    assert "CSC301" in rule.validate(ValidationContext([slot], set()))[0]
    assert rule.validate(ValidationContext([slot], {"CSC301"})) == []


def test_timetable_clash_detection():
    c1 = CourseSlot("CSC401", 3, "MON", 480, 600, 50, 10, ())
    c2 = CourseSlot("CSC413", 3, "MON", 540, 660, 50, 10, ())
    c3 = CourseSlot("CSC403", 3, "TUE", 540, 660, 50, 10, ())
    rule = TimetableClashRule()
    assert len(rule.validate(ValidationContext([c1, c2], set()))) == 1
    assert rule.validate(ValidationContext([c1, c3], set())) == []


def test_seat_capacity_rule():
    full_slot = CourseSlot("CSC417", 3, "WED", 840, 960, 30, 30, ())
    rule = SeatCapacityRule()
    assert len(rule.validate(ValidationContext([full_slot], set()))) == 1


# ==================== INTEGRATION TESTS: FULL END-TO-END FLOW ====================
def _auth_header(client: TestClient, email: str, password: str) -> dict:
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_rbac_blocks_student_from_admin_routes(client: TestClient):
    stu_headers = _auth_header(client, "u23cs1038@afit.edu.ng", "student123")
    res = client.get("/api/v1/admin/analytics", headers=stu_headers)
    assert res.status_code == 403


def test_end_to_end_registration_validation_submission_and_approval(client: TestClient):
    stu_headers = _auth_header(client, "u23cs1038@afit.edu.ng", "student123")
    adv_headers = _auth_header(client, "advisor@afit.edu.ng", "advisor123")

    courses = client.get("/api/v1/courses").json()
    by_code = {c["code"]: c for c in courses}

    # 1. Add CSC401 (valid)
    r1 = client.post(
        "/api/v1/registrations/me/items",
        json={"course_id": by_code["CSC401"]["id"]},
        headers=stu_headers,
    )
    assert r1.status_code == 200

    # 2. Attempt CSC413 (timetable clash with CSC401) -> 422
    r_clash = client.post(
        "/api/v1/registrations/me/items",
        json={"course_id": by_code["CSC413"]["id"]},
        headers=stu_headers,
    )
    assert r_clash.status_code == 422
    assert "Timetable clash" in r_clash.json()["detail"]

    # 3. Attempt CSC415 (unmet prerequisite CSC399) -> 422
    r_prereq = client.post(
        "/api/v1/registrations/me/items",
        json={"course_id": by_code["CSC415"]["id"]},
        headers=stu_headers,
    )
    assert r_prereq.status_code == 422
    assert "CSC399" in r_prereq.json()["detail"]

    # 4. Attempt CSC417 (full seat capacity) -> 422
    r_full = client.post(
        "/api/v1/registrations/me/items",
        json={"course_id": by_code["CSC417"]["id"]},
        headers=stu_headers,
    )
    assert r_full.status_code == 422
    assert "capacity" in r_full.json()["detail"]

    # 5. Add 5 more valid courses to hit 18 CU (within 15..24 CU)
    for code in ["CSC403", "CSC405", "CSC407", "CSC409", "CSC411"]:
        res = client.post(
            "/api/v1/registrations/me/items",
            json={"course_id": by_code[code]["id"]},
            headers=stu_headers,
        )
        assert res.status_code == 200

    # 6. Submit slip
    sub = client.post("/api/v1/registrations/me/submit", headers=stu_headers)
    assert sub.status_code == 200
    reg_id = sub.json()["id"]
    assert sub.json()["status"] == "SUBMITTED"
    assert sub.json()["total_credits"] == 18

    # 7. Advisor approves slip
    app_res = client.post(
        f"/api/v1/advisor/submissions/{reg_id}/decision",
        json={"decision": "APPROVED", "remark": "All 400L core courses verified."},
        headers=adv_headers,
    )
    assert app_res.status_code == 200
    assert app_res.json()["status"] == "APPROVED"


def test_admin_course_creation_and_analytics(client: TestClient):
    adm_headers = _auth_header(client, "admin@afit.edu.ng", "admin123")
    res = client.post(
        "/api/v1/admin/courses",
        json={
            "code": "CSC499",
            "title": "Final Year Research Project",
            "credit_units": 6,
            "level": 400,
            "capacity": 80,
            "day_of_week": "SAT",
            "start_time": "09:00",
            "end_time": "12:00",
            "prerequisites": ["CSC301"],
        },
        headers=adm_headers,
    )
    assert res.status_code == 201
    stats = client.get("/api/v1/admin/analytics", headers=adm_headers)
    assert stats.status_code == 200
    assert stats.json()["total_courses"] >= 11
