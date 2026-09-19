import io
import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Tuple
from backend.db import get_db
from backend.service import create_employee, create_task, record_history_event

logger = logging.getLogger("workwise.imports")

REQUIRED_HEADERS = {
    "employees": ["name", "email", "skills"],
    "tasks": ["title", "required_skills", "estimated_hours", "deadline"],
    "events": ["event_type", "task_id", "employee_id", "timestamp"]
}

def parse_and_validate_csv(file_content: bytes, file_type: str, filename: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Parses CSV content, validates headers and rows, returns (summary, valid_rows, errors).
    """
    text = file_content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    fieldnames = [f.strip().lower() for f in (reader.fieldnames or [])]

    req_headers = REQUIRED_HEADERS.get(file_type, [])
    missing_headers = [h for h in req_headers if h not in fieldnames]

    errors = []
    valid_rows = []

    if missing_headers:
        errors.append({
            "row_index": 0,
            "field": "headers",
            "message": f"Missing required headers: {', '.join(missing_headers)}"
        })
        return {
            "file_type": file_type,
            "filename": filename,
            "total_rows": 0,
            "valid_rows": 0,
            "invalid_rows": 1,
            "errors": errors
        }, [], errors

    conn = get_db()
    cursor = conn.cursor()
    existing_emails = set()
    if file_type == "employees":
        cursor.execute("SELECT email FROM employees")
        existing_emails = {r["email"].lower() for r in cursor.fetchall()}
    conn.close()

    seen_emails_in_file = set()

    for idx, row in enumerate(reader, 1):
        row_errors = []
        row_clean = {k.strip().lower(): (v.strip() if v else "") for k, v in row.items()}

        if file_type == "employees":
            email = row_clean.get("email", "").lower()
            if not row_clean.get("name"):
                row_errors.append("Name is required")
            if not email or "@" not in email:
                row_errors.append("Valid email is required")
            elif email in existing_emails or email in seen_emails_in_file:
                row_errors.append(f"Duplicate email '{email}' already exists")
            else:
                seen_emails_in_file.add(email)

            if not row_clean.get("skills"):
                row_errors.append("Skills are required")

        elif file_type == "tasks":
            if not row_clean.get("title"):
                row_errors.append("Task title is required")
            if not row_clean.get("required_skills"):
                row_errors.append("Required skills are required")
            try:
                est = float(row_clean.get("estimated_hours", 0))
                if est <= 0:
                    row_errors.append("Estimated hours must be > 0")
            except ValueError:
                row_errors.append("Estimated hours must be a valid number")

            deadline = row_clean.get("deadline", "")
            if not deadline:
                row_errors.append("Deadline is required")

        elif file_type == "events":
            if not row_clean.get("event_type"):
                row_errors.append("Event type is required")
            if not row_clean.get("timestamp"):
                row_errors.append("Timestamp is required")

        if row_errors:
            for err in row_errors:
                errors.append({"row_index": idx, "row_data": row_clean, "message": err})
        else:
            valid_rows.append(row_clean)

    summary = {
        "file_type": file_type,
        "filename": filename,
        "total_rows": len(valid_rows) + len(errors),
        "valid_rows": len(valid_rows),
        "invalid_rows": len(errors),
        "errors": errors
    }
    return summary, valid_rows, errors

def process_csv_import(file_content: bytes, file_type: str, filename: str, actor: str = "Manager") -> Dict[str, Any]:
    """
    Validates CSV and transactionally commits valid rows to SQLite and Excel log.
    """
    summary, valid_rows, errors = parse_and_validate_csv(file_content, file_type, filename)
    if not valid_rows:
        return {
            "status": "failed",
            "message": "No valid rows to import",
            "summary": summary
        }

    conn = get_db()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    imported_count = 0

    try:
        if file_type == "employees":
            for r in valid_rows:
                emp_data = {
                    "name": r["name"],
                    "email": r["email"],
                    "skills": r["skills"],
                    "location": r.get("location", "Remote"),
                    "working_hours_per_week": float(r.get("working_hours_per_week", 40.0)),
                    "working_window_start": r.get("working_window_start", "09:00"),
                    "working_window_end": r.get("working_window_end", "17:00"),
                    "timezone": r.get("timezone", "UTC"),
                    "is_active": r.get("is_active", "true").lower() in ["true", "1", "yes"],
                    "is_available": True
                }
                create_employee(emp_data, actor=actor)
                imported_count += 1

        elif file_type == "tasks":
            for r in valid_rows:
                task_data = {
                    "title": r["title"],
                    "description": r.get("description", ""),
                    "required_skills": r["required_skills"],
                    "location": r.get("location", ""),
                    "estimated_hours": float(r["estimated_hours"]),
                    "priority": r.get("priority", "Medium"),
                    "urgency": r.get("urgency", "Medium"),
                    "deadline": r["deadline"],
                    "sla_hours": float(r.get("sla_hours", 24.0))
                }
                create_task(task_data, actor=actor)
                imported_count += 1

        elif file_type == "events":
            for r in valid_rows:
                record_history_event(
                    conn,
                    event_type=r["event_type"],
                    task_id=int(r["task_id"]) if r.get("task_id") else None,
                    employee_id=int(r["employee_id"]) if r.get("employee_id") else None,
                    trigger_reason=r.get("reason", "CSV Import"),
                    actor=actor,
                    timestamp=r.get("timestamp", now),
                    notes=f"Imported event from CSV '{filename}'"
                )
                imported_count += 1

        # Record import batch in import_records
        cursor.execute("""
            INSERT INTO import_records (filename, file_type, imported_at, rows_count, status, error_log)
            VALUES (?, ?, ?, ?, 'confirmed', ?)
        """, (filename, file_type, now, imported_count, json.dumps(errors)))

        conn.commit()
        conn.close()

        return {
            "status": "success",
            "message": f"Successfully imported {imported_count} record(s) from {filename}",
            "imported_count": imported_count,
            "errors_count": len(errors),
            "errors": errors
        }

    except Exception as e:
        conn.rollback()
        conn.close()
        logger.error(f"Error processing CSV import {filename}: {str(e)}")
        return {
            "status": "error",
            "message": f"CSV import failed: {str(e)}",
            "errors": errors
        }
