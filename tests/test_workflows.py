import os
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from backend.main import app
from backend.db import init_db, get_db
from backend.excel_sync import get_default_excel_path
import openpyxl

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    """
    Sets up a disposable test SQLite database and disposable Excel file.
    """
    test_db_path = tmp_path / "workwise_test.db"
    test_excel_path = tmp_path / "allocation_history_test.xlsx"

    monkeypatch.setattr("backend.db.DB_PATH", test_db_path)
    monkeypatch.setattr("backend.excel_sync.get_default_excel_path", lambda: test_excel_path)

    init_db()
    yield

def test_employee_crud_and_persistence():
    # Create employee
    payload = {
        "name": "Test Engineer Alice",
        "email": "alice_test@example.com",
        "skills": "Python:4,FastAPI:3",
        "location": "New York",
        "working_hours_per_week": 40.0
    }
    res = client.post("/api/employees", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Test Engineer Alice"
    assert data["id"] is not None

    # Fetch employees list
    res_list = client.get("/api/employees")
    assert res_list.status_code == 200
    emps = res_list.json()
    assert len(emps) == 1
    assert emps[0]["remaining_capacity"] == 40.0

def test_task_lifecycle_and_allocation():
    # 1. Create 2 employees
    e1 = client.post("/api/employees", json={
        "name": "Senior Python Dev", "email": "senior@example.com",
        "skills": "Python:5,FastAPI:4", "location": "New York", "working_hours_per_week": 40.0
    }).json()

    e2 = client.post("/api/employees", json={
        "name": "Junior Dev", "email": "junior@example.com",
        "skills": "Python:2", "location": "London", "working_hours_per_week": 40.0
    }).json()

    # 2. Create high priority task
    t1 = client.post("/api/tasks", json={
        "title": "Build Critical API",
        "description": "Implement authentication API",
        "required_skills": "Python:4,FastAPI:3",
        "location": "New York",
        "estimated_hours": 15.0,
        "priority": "High",
        "urgency": "High",
        "deadline": "2026-10-01T17:00:00"
    }).json()

    # 3. Generate recommendation
    rec_res = client.post(f"/api/tasks/{t1['id']}/recommend")
    assert rec_res.status_code == 200
    cycle = rec_res.json()
    assert len(cycle["candidates"]) >= 2

    # Verify constraint evaluation: e1 should pass, e2 should fail skill proficiency constraint
    cand1 = next(c for c in cycle["candidates"] if c["employee_id"] == e1["id"])
    cand2 = next(c for c in cycle["candidates"] if c["employee_id"] == e2["id"])

    assert cand1["hard_constraints_passed"] is True
    assert cand2["hard_constraints_passed"] is False

    # 4. Approve qualified candidate
    app_res = client.post(f"/api/recommendations/{cycle['cycle_id']}/approve?candidate_employee_id={e1['id']}")
    assert app_res.status_code == 200

    # Verify task is assigned and employee capacity updated
    updated_t1 = client.get(f"/api/tasks/{t1['id']}").json()
    assert updated_t1["status"] == "assigned"
    assert updated_t1["assigned_employee_id"] == e1["id"]

    updated_e1 = client.get(f"/api/employees/{e1['id']}").json()
    assert updated_e1["current_workload"] == 15.0
    assert updated_e1["remaining_capacity"] == 25.0

    # 5. Complete task
    comp_res = client.post(f"/api/tasks/{t1['id']}/complete")
    assert comp_res.status_code == 200
    comp_task = comp_res.json()
    assert comp_task["status"] == "completed"

    # Verify workload released exactly once
    freed_e1 = client.get(f"/api/employees/{e1['id']}").json()
    assert freed_e1["current_workload"] == 0.0
    assert freed_e1["remaining_capacity"] == 40.0

def test_rejection_queue_advancement():
    # Create 2 qualified employees
    e1 = client.post("/api/employees", json={
        "name": "Dev 1", "email": "dev1@example.com", "skills": "React:4", "location": "Remote", "working_hours_per_week": 40.0
    }).json()
    e2 = client.post("/api/employees", json={
        "name": "Dev 2", "email": "dev2@example.com", "skills": "React:4", "location": "Remote", "working_hours_per_week": 40.0
    }).json()

    task = client.post("/api/tasks", json={
        "title": "Build Dashboard Component", "required_skills": "React:3",
        "estimated_hours": 8.0, "deadline": "2026-10-05T17:00:00"
    }).json()

    cycle = client.post(f"/api/tasks/{task['id']}/recommend").json()

    # Reject top candidate
    top_cand = cycle["candidates"][0]
    rej_res = client.post(f"/api/recommendations/{cycle['cycle_id']}/reject?candidate_employee_id={top_cand['employee_id']}")
    assert rej_res.status_code == 200
    updated_cycle = rej_res.json()

    # Rejected candidate marked rejected
    rej_cand = next(c for c in updated_cycle["candidates"] if c["employee_id"] == top_cand["employee_id"])
    assert rej_cand["status"] == "rejected"

def test_dynamic_reallocation_on_employee_unavailability():
    e1 = client.post("/api/employees", json={
        "name": "Dev Lead", "email": "lead@example.com", "skills": "Python:4", "location": "Remote", "working_hours_per_week": 40.0
    }).json()

    task = client.post("/api/tasks", json={
        "title": "Backend Refactor", "required_skills": "Python:3",
        "estimated_hours": 12.0, "deadline": "2026-10-02T17:00:00"
    }).json()

    cycle = client.post(f"/api/tasks/{task['id']}/recommend").json()
    client.post(f"/api/recommendations/{cycle['cycle_id']}/approve?candidate_employee_id={e1['id']}")

    # Mark assigned employee unavailable
    client.patch(f"/api/employees/{e1['id']}", json={"is_available": False})

    # Task should now be flagged at_risk
    updated_task = client.get(f"/api/tasks/{task['id']}").json()
    assert updated_task["status"] == "at_risk"
    assert updated_task["is_at_risk"] is True
