import pytest
from backend.ollama_client import check_ollama_status
from backend.assistant import process_assistant_message, extract_employee_entities_from_text
from backend.db import init_db

def test_ollama_status_check():
    status = check_ollama_status()
    assert isinstance(status, dict)
    assert "online" in status
    assert "model" in status
    assert status["model"] == "gemma3:4b"

def test_extract_employee_entities():
    sample = "Add employee Sarah Connor, email sarah@skynet.com, skills Python:5, Machine Learning:4, location San Francisco, 40 hours"
    res = extract_employee_entities_from_text(sample)
    assert res is not None
    assert res["name"] == "Sarah Connor"
    assert res["email"] == "sarah@skynet.com"
    assert "Python:5" in res["skills"]
    assert res["location"] == "San Francisco"
    assert res["working_hours_per_week"] == 40.0

import uuid

def test_assistant_message_flow():
    init_db()
    # Test creation command with unique email
    u_email = f"john_{uuid.uuid4().hex[:6]}@skynet.com"
    prompt = f"Add employee John Connor, email {u_email}, skills Python:4, location Los Angeles, 35 hours"
    res = process_assistant_message(prompt, session_id="test_session")
    assert "reply" in res
    assert "John Connor" in res["reply"]
    assert res["model_name"] == "gemma3:4b"
