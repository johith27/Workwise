import os
import uuid
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from backend.db import get_db
from backend.engine import predict_candidate_rankings, evaluate_hard_constraints, parse_skills
from backend.excel_sync import append_history_row, rebuild_excel_from_sqlite

logger = logging.getLogger("workwise.service")

def current_iso() -> str:
    return datetime.now().isoformat()

def compute_employee_workload(cursor, employee_id: int) -> Tuple[float, int]:
    cursor.execute("""
        SELECT COALESCE(SUM(a.hours_remaining), 0.0) as total_workload,
               COUNT(a.id) as active_count
        FROM assignments a
        JOIN tasks t ON a.task_id = t.id
        WHERE a.employee_id = ? AND a.status = 'active' AND t.status IN ('assigned', 'pending', 'at_risk')
    """, (employee_id,))
    row = cursor.fetchone()
    return float(row["total_workload"]), int(row["active_count"])

def compute_historical_success_rate(cursor, employee_id: int) -> float:
    cursor.execute("""
        SELECT 
            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_count,
            COUNT(*) as total_count
        FROM assignments
        WHERE employee_id = ?
    """, (employee_id,))
    row = cursor.fetchone()
    if not row or row["total_count"] == 0:
        return 1.0
    return float(row["completed_count"]) / float(row["total_count"])

def record_history_event(
    conn,
    event_type: str,
    task_id: Optional[int] = None,
    task_title: Optional[str] = None,
    employee_id: Optional[int] = None,
    employee_name: Optional[str] = None,
    previous_employee_id: Optional[int] = None,
    previous_employee_name: Optional[str] = None,
    priority: Optional[str] = None,
    urgency: Optional[str] = None,
    deadline: Optional[str] = None,
    sla: Optional[str] = None,
    location: Optional[str] = None,
    estimated_hours: Optional[float] = None,
    remaining_hours_before: Optional[float] = None,
    remaining_hours_after: Optional[float] = None,
    matching_score_or_rank: Optional[str] = None,
    constraint_checks: Optional[str] = None,
    trigger_reason: Optional[str] = None,
    actor: str = "system",
    timestamp: Optional[str] = None,
    model_version: Optional[str] = None,
    notes: Optional[str] = None,
    before_snapshot: Optional[Dict[str, Any]] = None,
    after_snapshot: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    event_id = f"EVT-{uuid.uuid4().hex[:8].upper()}"
    event_timestamp = timestamp or current_iso()
    cursor = conn.cursor()

    before_json = json.dumps(before_snapshot) if before_snapshot else None
    after_json = json.dumps(after_snapshot) if after_snapshot else None

    cursor.execute("""
        INSERT INTO history (
            event_id, event_type, task_id, task_title, employee_id, employee_name,
            previous_employee_id, previous_employee_name, priority, urgency, deadline,
            sla, location, estimated_hours, remaining_hours_before, remaining_hours_after,
            matching_score_or_rank, constraint_checks, trigger_reason, actor, timestamp,
            model_version, notes, before_snapshot, after_snapshot
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        event_id, event_type, task_id, task_title, employee_id, employee_name,
        previous_employee_id, previous_employee_name, priority, urgency, deadline,
        str(sla) if sla is not None else None, location, estimated_hours,
        remaining_hours_before, remaining_hours_after, matching_score_or_rank,
        constraint_checks, trigger_reason, actor, event_timestamp, model_version, notes,
        before_json, after_json
    ))

    event_dict = {
        "event_id": event_id,
        "event_type": event_type,
        "task_id": task_id,
        "task_title": task_title,
        "employee_id": employee_id,
        "employee_name": employee_name,
        "previous_employee_id": previous_employee_id,
        "previous_employee_name": previous_employee_name,
        "priority": priority,
        "urgency": urgency,
        "deadline": deadline,
        "sla": str(sla) if sla is not None else "",
        "location": location,
        "estimated_hours": estimated_hours,
        "remaining_hours_before": remaining_hours_before,
        "remaining_hours_after": remaining_hours_after,
        "matching_score_or_rank": matching_score_or_rank,
        "constraint_checks": constraint_checks,
        "trigger_reason": trigger_reason,
        "actor": actor,
        "timestamp": event_timestamp,
        "model_version": model_version,
        "notes": notes
    }

    append_history_row(event_dict, db_conn=conn)
    return event_dict

# Employee Services
def get_all_employees(search: Optional[str] = None, skill_filter: Optional[str] = None, is_active: Optional[bool] = None) -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    query = "SELECT * FROM employees WHERE 1=1"
    params = []
    
    if is_active is not None:
        query += " AND is_active = ?"
        params.append(1 if is_active else 0)
    if search:
        query += " AND (name LIKE ? OR email LIKE ? OR location LIKE ?)"
        s_term = f"%{search}%"
        params.extend([s_term, s_term, s_term])
    
    query += " ORDER BY name ASC"
    cursor.execute(query, params)
    employees = [dict(r) for r in cursor.fetchall()]

    result = []
    for emp in employees:
        emp_id = emp["id"]
        workload, active_count = compute_employee_workload(cursor, emp_id)
        if skill_filter and skill_filter.lower() not in emp["skills"].lower():
            continue
        weekly_hours = float(emp.get("working_hours_per_week", 40.0))
        rem_cap = max(0.0, weekly_hours - workload)
        emp["current_workload"] = workload
        emp["remaining_capacity"] = rem_cap
        emp["active_assignments_count"] = active_count
        emp["is_active"] = bool(emp["is_active"])
        emp["is_available"] = bool(emp["is_available"])
        result.append(emp)
    conn.close()
    return result

def get_employee_by_id(employee_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM employees WHERE id = ?", (employee_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
    emp = dict(row)
    workload, active_count = compute_employee_workload(cursor, employee_id)
    weekly_hours = float(emp.get("working_hours_per_week", 40.0))
    emp["current_workload"] = workload
    emp["remaining_capacity"] = max(0.0, weekly_hours - workload)
    emp["active_assignments_count"] = active_count
    emp["is_active"] = bool(emp["is_active"])
    emp["is_available"] = bool(emp["is_available"])
    conn.close()
    return emp

def get_employee_profile(employee_id: int) -> Optional[Dict[str, Any]]:
    emp = get_employee_by_id(employee_id)
    if not emp:
        return None

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT a.*, t.title as task_title, t.estimated_hours, t.deadline, t.priority, t.status as task_status
        FROM assignments a
        JOIN tasks t ON a.task_id = t.id
        WHERE a.employee_id = ?
        ORDER BY a.id DESC
    """, (employee_id,))
    assignment_rows = [dict(r) for r in cursor.fetchall()]

    active_assignments = [a for a in assignment_rows if a["status"] == "active"]
    completed_assignments = [a for a in assignment_rows if a["status"] == "completed"]
    completed_count = len(completed_assignments)
    total_hours_delivered = sum(float(a.get("hours_allocated", 0.0)) for a in completed_assignments)

    audit_history = get_all_history_events(employee_id=employee_id, limit=50)

    conn.close()

    return {
        "employee": emp,
        "active_assignments": active_assignments,
        "completed_assignments_count": completed_count,
        "total_hours_delivered": total_hours_delivered,
        "assignment_history": assignment_rows,
        "audit_history": audit_history
    }

def create_employee(data: Dict[str, Any], actor: str = "Manager") -> Dict[str, Any]:
    conn = get_db()
    cursor = conn.cursor()
    now = current_iso()
    cursor.execute("""
        INSERT INTO employees (
            name, email, skills, location, working_hours_per_week,
            working_window_start, working_window_end, timezone, is_active, is_available, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["name"], data["email"], data["skills"], data.get("location", "Remote"),
        data.get("working_hours_per_week", 40.0), data.get("working_window_start", "09:00"),
        data.get("working_window_end", "17:00"), data.get("timezone", "UTC"),
        1 if data.get("is_active", True) else 0, 1 if data.get("is_available", True) else 0,
        now, now
    ))
    emp_id = cursor.lastrowid

    record_history_event(
        conn, event_type="employee_created", employee_id=emp_id, employee_name=data["name"],
        location=data.get("location", "Remote"), actor=actor, timestamp=now, notes=f"Created employee {data['name']}"
    )
    conn.commit()
    conn.close()

    return get_employee_by_id(emp_id)

def update_employee(employee_id: int, updates: Dict[str, Any], actor: str = "Manager") -> Optional[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    old_emp = get_employee_by_id(employee_id)
    if not old_emp:
        conn.close()
        return None

    set_clauses = []
    params = []
    for k, v in updates.items():
        if v is not None and k in ["name", "email", "skills", "location", "working_hours_per_week", "working_window_start", "working_window_end", "timezone", "is_active", "is_available"]:
            set_clauses.append(f"{k} = ?")
            params.append(1 if isinstance(v, bool) and v else (0 if isinstance(v, bool) else v))

    if set_clauses:
        now = current_iso()
        set_clauses.append("updated_at = ?")
        params.append(now)
        params.append(employee_id)
        cursor.execute(f"UPDATE employees SET {', '.join(set_clauses)} WHERE id = ?", params)
        conn.commit()

    new_emp = get_employee_by_id(employee_id)

    availability_changed = (old_emp["is_available"] and not new_emp["is_available"]) or (old_emp["is_active"] and not new_emp["is_active"])
    
    if availability_changed:
        trigger_reason = f"Employee {new_emp['name']} marked unavailable/deactivated"
        _trigger_dynamic_reallocation_for_employee(conn, new_emp, trigger_reason, actor)

    conn.close()
    return new_emp

def _trigger_dynamic_reallocation_for_employee(conn, employee: Dict[str, Any], trigger_reason: str, actor: str):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT t.* FROM tasks t
        JOIN assignments a ON a.task_id = t.id
        WHERE a.employee_id = ? AND a.status = 'active' AND t.status IN ('assigned', 'pending', 'at_risk')
    """, (employee["id"],))
    affected_tasks = [dict(r) for r in cursor.fetchall()]

    for task in affected_tasks:
        cursor.execute("UPDATE tasks SET status = 'at_risk', updated_at = datetime('now') WHERE id = ?", (task["id"],))

        record_history_event(
            conn, event_type="reevaluated", task_id=task["id"], task_title=task["title"],
            employee_id=employee["id"], employee_name=employee["name"], priority=task["priority"],
            urgency=task["urgency"], deadline=task["deadline"], location=task["location"],
            estimated_hours=task["estimated_hours"], trigger_reason=trigger_reason,
            actor=actor, notes=f"Task flagged at-risk due to employee status change: {trigger_reason}"
        )

        generate_recommendation(task["id"], trigger_reason=trigger_reason, actor=actor, conn=conn)

# Task Services
def get_all_tasks(status: Optional[str] = None, priority: Optional[str] = None, search: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    query = """
        SELECT t.*,
               e.name as assigned_employee_name,
               ce.name as completed_by_employee_name
        FROM tasks t
        LEFT JOIN employees e ON t.assigned_employee_id = e.id
        LEFT JOIN employees ce ON t.completed_by_employee_id = ce.id
        WHERE 1=1
    """
    params = []
    if status:
        query += " AND t.status = ?"
        params.append(status)
    if priority:
        query += " AND t.priority = ?"
        params.append(priority)
    if search:
        query += " AND (t.title LIKE ? OR t.description LIKE ? OR t.required_skills LIKE ?)"
        s_term = f"%{search}%"
        params.extend([s_term, s_term, s_term])
    
    query += " ORDER BY t.created_at DESC"
    cursor.execute(query, params)
    tasks = [dict(r) for r in cursor.fetchall()]

    for t in tasks:
        t["is_at_risk"] = t["status"] == "at_risk"
        t["at_risk_reason"] = "Assigned employee is unavailable or overloaded" if t["is_at_risk"] else None

    conn.close()
    return tasks

def get_task_by_id(task_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT t.*,
               e.name as assigned_employee_name,
               ce.name as completed_by_employee_name
        FROM tasks t
        LEFT JOIN employees e ON t.assigned_employee_id = e.id
        LEFT JOIN employees ce ON t.completed_by_employee_id = ce.id
        WHERE t.id = ?
    """, (task_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    task = dict(row)
    task["is_at_risk"] = task["status"] == "at_risk"
    task["at_risk_reason"] = "Assigned employee is unavailable or overloaded" if task["is_at_risk"] else None
    return task

def create_task(data: Dict[str, Any], actor: str = "Manager") -> Dict[str, Any]:
    conn = get_db()
    cursor = conn.cursor()
    now = current_iso()
    cursor.execute("""
        INSERT INTO tasks (
            title, description, required_skills, location, estimated_hours,
            priority, urgency, deadline, sla_hours, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
    """, (
        data["title"], data.get("description", ""), data["required_skills"],
        data.get("location", ""), data["estimated_hours"], data.get("priority", "Medium"),
        data.get("urgency", "Medium"), data["deadline"], data.get("sla_hours", 24.0),
        now, now
    ))
    task_id = cursor.lastrowid

    record_history_event(
        conn, event_type="task_created", task_id=task_id, task_title=data["title"],
        priority=data.get("priority", "Medium"), urgency=data.get("urgency", "Medium"),
        deadline=data["deadline"], sla=data.get("sla_hours", 24.0), location=data.get("location", ""),
        estimated_hours=data["estimated_hours"], actor=actor, timestamp=now, notes=f"Created task '{data['title']}'"
    )
    conn.commit()

    generate_recommendation(task_id, trigger_reason="Initial task creation", actor=actor, conn=conn)
    conn.close()

    return get_task_by_id(task_id)

def update_task(task_id: int, updates: Dict[str, Any], actor: str = "Manager") -> Optional[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    old_task = get_task_by_id(task_id)
    if not old_task:
        conn.close()
        return None

    set_clauses = []
    params = []
    for k in ["title", "description", "required_skills", "location", "estimated_hours", "priority", "urgency", "deadline", "sla_hours", "status"]:
        if k in updates and updates[k] is not None:
            set_clauses.append(f"{k} = ?")
            params.append(updates[k])

    if set_clauses:
        now = current_iso()
        set_clauses.append("updated_at = ?")
        params.append(now)
        params.append(task_id)
        cursor.execute(f"UPDATE tasks SET {', '.join(set_clauses)} WHERE id = ?", params)
        conn.commit()

    new_task = get_task_by_id(task_id)

    if new_task.get("assigned_employee_id"):
        assigned_emp = get_employee_by_id(new_task["assigned_employee_id"])
        if assigned_emp:
            workload, _ = compute_employee_workload(cursor, assigned_emp["id"])
            passed, _, reason = evaluate_hard_constraints(new_task, assigned_emp, workload - new_task["estimated_hours"])
            if not passed:
                cursor.execute("UPDATE tasks SET status = 'at_risk', updated_at = datetime('now') WHERE id = ?", (task_id,))
                conn.commit()
                generate_recommendation(task_id, trigger_reason=f"Task updated: {reason}", actor=actor, conn=conn)

    conn.close()
    return new_task

def complete_task(task_id: int, actor: str = "Manager", employee_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    task = get_task_by_id(task_id)
    if not task:
        conn.close()
        return None

    if task["status"] == "completed":
        conn.close()
        return task

    completing_emp_id = employee_id or task.get("assigned_employee_id")
    completing_emp_name = "Unassigned"
    if completing_emp_id:
        cursor.execute("SELECT name FROM employees WHERE id = ?", (completing_emp_id,))
        erow = cursor.fetchone()
        if erow:
            completing_emp_name = erow["name"]

    now = current_iso()

    rem_before = 0.0
    if completing_emp_id:
        workload_before, _ = compute_employee_workload(cursor, completing_emp_id)
        rem_before = workload_before

    cursor.execute("""
        UPDATE assignments
        SET status = 'completed', hours_remaining = 0.0, completed_at = ?
        WHERE task_id = ? AND status = 'active'
    """, (now, task_id))

    cursor.execute("""
        UPDATE tasks
        SET status = 'completed', completed_at = ?, completed_by_employee_id = ?, completed_by_actor = ?, updated_at = ?
        WHERE id = ?
    """, (now, completing_emp_id, actor, now, task_id))

    rem_after = 0.0
    if completing_emp_id:
        workload_after, _ = compute_employee_workload(cursor, completing_emp_id)
        rem_after = workload_after

    record_history_event(
        conn, event_type="completed", task_id=task_id, task_title=task["title"],
        employee_id=completing_emp_id, employee_name=completing_emp_name,
        priority=task["priority"], urgency=task["urgency"], deadline=task["deadline"],
        sla=task["sla_hours"], location=task["location"], estimated_hours=task["estimated_hours"],
        remaining_hours_before=rem_before, remaining_hours_after=rem_after,
        trigger_reason="Manager/User marked task as completed", actor=actor, timestamp=now,
        notes=f"Task '{task['title']}' completed by {completing_emp_name} (Logged by {actor})"
    )

    conn.commit()
    updated_task = get_task_by_id(task_id)
    conn.close()
    return updated_task

def cancel_task(task_id: int, actor: str = "Manager", reason: str = "Cancelled by user") -> Optional[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    task = get_task_by_id(task_id)
    if not task:
        conn.close()
        return None

    now = current_iso()
    assigned_emp_id = task.get("assigned_employee_id")
    assigned_emp_name = task.get("assigned_employee_name")

    cursor.execute("""
        UPDATE assignments
        SET status = 'cancelled', hours_remaining = 0.0, unassigned_at = ?, unassigned_reason = ?
        WHERE task_id = ? AND status = 'active'
    """, (now, reason, task_id))

    cursor.execute("""
        UPDATE tasks
        SET status = 'cancelled', updated_at = ?
        WHERE id = ?
    """, (now, task_id))

    record_history_event(
        conn, event_type="cancelled", task_id=task_id, task_title=task["title"],
        employee_id=assigned_emp_id, employee_name=assigned_emp_name,
        priority=task["priority"], urgency=task["urgency"], deadline=task["deadline"],
        sla=task["sla_hours"], location=task["location"], estimated_hours=task["estimated_hours"],
        trigger_reason=reason, actor=actor, timestamp=now, notes=f"Task '{task['title']}' cancelled. Reason: {reason}"
    )

    conn.commit()
    updated_task = get_task_by_id(task_id)
    conn.close()
    return updated_task

# Recommendation Cycle Services
def generate_recommendation(task_id: int, trigger_reason: str = "manual_request", actor: str = "system", conn=None) -> Dict[str, Any]:
    close_conn = False
    if conn is None:
        conn = get_db()
        close_conn = True

    cursor = conn.cursor()
    task = get_task_by_id(task_id)
    if not task:
        if close_conn: conn.close()
        raise ValueError(f"Task ID {task_id} not found")

    employees = get_all_employees()
    workload_map = {e["id"]: e["current_workload"] for e in employees}
    hist_rates_map = {e["id"]: compute_historical_success_rate(cursor, e["id"]) for e in employees}

    cursor.execute("""
        UPDATE recommendation_cycles SET status = 'superseded' WHERE task_id = ? AND status = 'active'
    """, (task_id,))

    ranked_candidates, model_version = predict_candidate_rankings(
        task, employees, workload_map, hist_rates_map
    )

    now = current_iso()
    cursor.execute("""
        INSERT INTO recommendation_cycles (task_id, created_at, status, model_version, trigger_reason)
        VALUES (?, ?, 'active', ?, ?)
    """, (task_id, now, model_version, trigger_reason))
    cycle_id = cursor.lastrowid

    for cand in ranked_candidates:
        cursor.execute("""
            INSERT INTO ranked_candidates (
                cycle_id, employee_id, rank, score, hard_constraints_passed, constraint_details, status, rejection_reason
            ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
        """, (
            cycle_id, cand["employee_id"], cand["rank"], cand["score"],
            1 if cand["hard_constraints_passed"] else 0,
            json.dumps(cand["constraint_details"]),
            cand["rejection_reason"]
        ))

    conn.commit()

    qualifying_count = sum(1 for c in ranked_candidates if c["hard_constraints_passed"])
    no_qualifying_reason = None
    if qualifying_count == 0:
        reasons = [c["rejection_reason"] for c in ranked_candidates if c["rejection_reason"]]
        no_qualifying_reason = "No eligible candidate qualifies. Disqualification breakdown:\n- " + "\n- ".join(set(reasons)) if reasons else "No active employees available."

    top_cand = ranked_candidates[0] if ranked_candidates else None
    top_score_str = f"Rank #{top_cand['rank']} (Score: {top_cand['score']:.4f})" if top_cand else "N/A"
    top_checks_str = "Passed" if top_cand and top_cand["hard_constraints_passed"] else (top_cand["rejection_reason"] if top_cand else "Failed")

    record_history_event(
        conn, event_type="reevaluated", task_id=task_id, task_title=task["title"],
        employee_id=top_cand["employee_id"] if top_cand else None,
        employee_name=top_cand["employee_name"] if top_cand else None,
        priority=task["priority"], urgency=task["urgency"], deadline=task["deadline"],
        sla=task["sla_hours"], location=task["location"], estimated_hours=task["estimated_hours"],
        matching_score_or_rank=top_score_str, constraint_checks=top_checks_str,
        trigger_reason=trigger_reason, actor=actor, timestamp=now, model_version=model_version,
        notes=no_qualifying_reason or f"Recommendation cycle {cycle_id} generated. {qualifying_count} candidate(s) passed hard constraints."
    )

    conn.commit()
    cycle_res = get_recommendation_cycle_by_id(cycle_id)
    if close_conn: conn.close()
    return cycle_res

def get_recommendation_cycle_by_id(cycle_id: int) -> Dict[str, Any]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT rc.*, t.title as task_title
        FROM recommendation_cycles rc
        JOIN tasks t ON rc.task_id = t.id
        WHERE rc.id = ?
    """, (cycle_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Cycle ID {cycle_id} not found")
    
    cycle = dict(row)
    cycle["cycle_id"] = cycle["id"]
    cursor.execute("""
        SELECT rcand.*, e.name as employee_name, e.working_hours_per_week
        FROM ranked_candidates rcand
        JOIN employees e ON rcand.employee_id = e.id
        WHERE rcand.cycle_id = ?
        ORDER BY rcand.rank ASC
    """, (cycle_id,))
    candidates_rows = cursor.fetchall()
    
    candidates = []
    for c in candidates_rows:
        c_dict = dict(c)
        c_dict["hard_constraints_passed"] = bool(c_dict["hard_constraints_passed"])
        c_dict["constraint_details"] = json.loads(c_dict["constraint_details"])
        workload, _ = compute_employee_workload(cursor, c_dict["employee_id"])
        weekly_h = float(c_dict.get("working_hours_per_week", 40.0))
        c_dict["employee_current_workload"] = workload
        c_dict["employee_remaining_capacity"] = max(0.0, weekly_h - workload)
        candidates.append(c_dict)

    qualifying_count = sum(1 for c in candidates if c["hard_constraints_passed"])
    no_qualifying_reason = None
    if qualifying_count == 0:
        reasons = [c["rejection_reason"] for c in candidates if c["rejection_reason"]]
        no_qualifying_reason = "No candidate qualifies hard constraint check:\n- " + "\n- ".join(set(reasons)) if reasons else "No employees available."

    cycle["candidates"] = candidates
    cycle["no_qualifying_reason"] = no_qualifying_reason
    conn.close()
    return cycle

def get_active_recommendation_for_task(task_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id FROM recommendation_cycles
        WHERE task_id = ? AND status = 'active'
        ORDER BY id DESC LIMIT 1
    """, (task_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return get_recommendation_cycle_by_id(row["id"])

def get_all_pending_recommendations() -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id FROM recommendation_cycles
        WHERE status = 'active'
        ORDER BY id DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    result = []
    for r in rows:
        try:
            result.append(get_recommendation_cycle_by_id(r["id"]))
        except Exception:
            pass
    return result

def approve_candidate(cycle_id: int, candidate_employee_id: int, actor: str = "Manager", reason: Optional[str] = None) -> Dict[str, Any]:
    conn = get_db()
    cursor = conn.cursor()
    
    cycle = get_recommendation_cycle_by_id(cycle_id)
    task_id = cycle["task_id"]
    task = get_task_by_id(task_id)
    candidate_emp = get_employee_by_id(candidate_employee_id)

    if not candidate_emp:
        conn.close()
        raise ValueError("Candidate employee not found")

    workload_before, _ = compute_employee_workload(cursor, candidate_employee_id)
    passed, _, constraint_reason = evaluate_hard_constraints(task, candidate_emp, workload_before)

    if not passed:
        conn.close()
        raise ValueError(f"Approval rejected: Candidate no longer satisfies constraints ({constraint_reason})")

    prev_emp_id = task.get("assigned_employee_id")
    prev_emp_name = task.get("assigned_employee_name")
    is_reassignment = prev_emp_id is not None and prev_emp_id != candidate_employee_id

    now = current_iso()

    if is_reassignment:
        cursor.execute("""
            UPDATE assignments
            SET status = 'reassigned', hours_remaining = 0.0, unassigned_at = ?, unassigned_reason = ?
            WHERE task_id = ? AND status = 'active'
        """, (now, f"Reassigned to {candidate_emp['name']} by {actor}", task_id))

    cursor.execute("""
        INSERT INTO assignments (
            task_id, employee_id, assigned_at, assigned_by, status, hours_allocated, hours_remaining
        ) VALUES (?, ?, ?, ?, 'active', ?, ?)
    """, (task_id, candidate_employee_id, now, actor, task["estimated_hours"], task["estimated_hours"]))

    cursor.execute("""
        UPDATE tasks
        SET status = 'assigned', assigned_employee_id = ?, assigned_at = ?, updated_at = ?
        WHERE id = ?
    """, (candidate_employee_id, now, now, task_id))

    cursor.execute("""
        UPDATE ranked_candidates SET status = 'approved' WHERE cycle_id = ? AND employee_id = ?
    """, (cycle_id, candidate_employee_id))

    cursor.execute("""
        UPDATE recommendation_cycles SET status = 'resolved' WHERE id = ?
    """, (cycle_id,))

    workload_after, _ = compute_employee_workload(cursor, candidate_employee_id)

    score_str = "Approved"
    for c in cycle["candidates"]:
        if c["employee_id"] == candidate_employee_id:
            score_str = f"Rank #{c['rank']} (Score: {c['score']:.4f})"
            break

    event_type = "reassigned" if is_reassignment else "approved"
    trigger_desc = f"Manager approval ({reason})" if reason else "Manager approved allocation"

    record_history_event(
        conn, event_type=event_type, task_id=task_id, task_title=task["title"],
        employee_id=candidate_employee_id, employee_name=candidate_emp["name"],
        previous_employee_id=prev_emp_id if is_reassignment else None,
        previous_employee_name=prev_emp_name if is_reassignment else None,
        priority=task["priority"], urgency=task["urgency"], deadline=task["deadline"],
        sla=task["sla_hours"], location=task["location"], estimated_hours=task["estimated_hours"],
        remaining_hours_before=workload_before, remaining_hours_after=workload_after,
        matching_score_or_rank=score_str, constraint_checks="Passed",
        trigger_reason=trigger_desc, actor=actor, timestamp=now,
        model_version=cycle["model_version"], notes=reason or f"Approved assignment of {task['title']} to {candidate_emp['name']}"
    )

    conn.commit()
    updated_cycle = get_recommendation_cycle_by_id(cycle_id)
    conn.close()
    return updated_cycle

def reject_candidate(cycle_id: int, candidate_employee_id: int, actor: str = "Manager", reason: Optional[str] = None) -> Dict[str, Any]:
    conn = get_db()
    cursor = conn.cursor()
    
    cycle = get_recommendation_cycle_by_id(cycle_id)
    task_id = cycle["task_id"]
    task = get_task_by_id(task_id)
    candidate_emp = get_employee_by_id(candidate_employee_id)
    cand_name = candidate_emp["name"] if candidate_emp else f"Employee #{candidate_employee_id}"

    reject_reason_text = reason or "Manager rejected recommendation"

    cursor.execute("""
        UPDATE ranked_candidates
        SET status = 'rejected', rejection_reason = ?
        WHERE cycle_id = ? AND employee_id = ?
    """, (reject_reason_text, cycle_id, candidate_employee_id))

    record_history_event(
        conn, event_type="rejected", task_id=task_id, task_title=task["title"],
        employee_id=candidate_employee_id, employee_name=cand_name,
        priority=task["priority"], urgency=task["urgency"], deadline=task["deadline"],
        sla=task["sla_hours"], location=task["location"], estimated_hours=task["estimated_hours"],
        trigger_reason=f"Manager rejected candidate ({reject_reason_text})", actor=actor, timestamp=current_iso(),
        model_version=cycle["model_version"], notes=f"Manager rejected {cand_name} for task {task['title']}. Advancing to next eligible candidate."
    )

    conn.commit()
    updated_cycle = get_recommendation_cycle_by_id(cycle_id)
    conn.close()
    return updated_cycle

def get_dashboard_summary() -> Dict[str, Any]:
    conn = get_db()
    cursor = conn.cursor()

    employees = get_all_employees()
    tasks = get_all_tasks()
    history_events = get_all_history_events(limit=10)
    pending_recs = get_all_pending_recommendations()

    total_employees = len(employees)
    available_employees = sum(1 for e in employees if e["is_active"] and e["is_available"])

    pending_tasks = sum(1 for t in tasks if t["status"] in ["pending", "at_risk"])
    active_tasks = sum(1 for t in tasks if t["status"] == "assigned")
    completed_tasks = sum(1 for t in tasks if t["status"] == "completed")
    at_risk_tasks = sum(1 for t in tasks if t["status"] == "at_risk")

    total_capacity = sum(float(e["working_hours_per_week"]) for e in employees if e["is_active"])
    total_workload = sum(e["current_workload"] for e in employees if e["is_active"])
    avg_utilization = (total_workload / total_capacity * 100.0) if total_capacity > 0 else 0.0

    at_risk_list = [t for t in tasks if t["status"] == "at_risk"]

    cursor.execute("""
        SELECT t.*,
               e.name as assigned_employee_name,
               ce.name as completed_by_employee_name
        FROM tasks t
        LEFT JOIN employees e ON t.assigned_employee_id = e.id
        LEFT JOIN employees ce ON t.completed_by_employee_id = ce.id
        WHERE t.status = 'completed' AND t.completed_at IS NOT NULL
        ORDER BY t.completed_at DESC LIMIT 1
    """)
    latest_task_row = cursor.fetchone()
    latest_completed_task = dict(latest_task_row) if latest_task_row else None

    latest_completed_employee = None
    if latest_completed_task and latest_completed_task.get("completed_by_employee_id"):
        latest_completed_employee = get_employee_by_id(latest_completed_task["completed_by_employee_id"])

    conn.close()

    return {
        "total_employees": total_employees,
        "available_employees": available_employees,
        "pending_tasks": pending_tasks,
        "active_tasks": active_tasks,
        "completed_tasks": completed_tasks,
        "at_risk_tasks": at_risk_tasks,
        "avg_capacity_utilization": round(avg_utilization, 1),
        "pending_recommendations": pending_recs,
        "at_risk_task_list": at_risk_list,
        "recent_activity": history_events,
        "latest_completed_task": latest_completed_task,
        "latest_completed_employee": latest_completed_employee
    }

def get_all_history_events(
    employee_id: Optional[int] = None,
    task_id: Optional[int] = None,
    event_type: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    query = "SELECT * FROM history WHERE 1=1"
    params = []

    if employee_id:
        query += " AND (employee_id = ? OR previous_employee_id = ?)"
        params.extend([employee_id, employee_id])
    if task_id:
        query += " AND task_id = ?"
        params.append(task_id)
    if event_type:
        query += " AND event_type = ?"
        params.append(event_type)
    if search:
        query += " AND (task_title LIKE ? OR employee_name LIKE ? OR notes LIKE ? OR actor LIKE ?)"
        s_term = f"%{search}%"
        params.extend([s_term, s_term, s_term, s_term])

    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def get_system_settings() -> Dict[str, Any]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM settings")
    s_map = {row["key"]: row["value"] for row in cursor.fetchall()}

    cursor.execute("SELECT COUNT(*) as row_count FROM history")
    row_count = int(cursor.fetchone()["row_count"])

    model_path = Path(__file__).resolve().parent.parent / "models" / "workforce_random_forest.pkl"
    model_status = "Trained & Configured" if model_path.exists() else "MODEL_NOT_CONFIGURED (Using Heuristic Ranking)"

    conn.close()
    return {
        "excel_log_path": s_map.get("excel_log_path", ""),
        "last_excel_sync": s_map.get("last_excel_sync", "Never"),
        "excel_sync_status": s_map.get("excel_sync_status", "Never synced"),
        "excel_row_count": row_count,
        "allocation_policy": s_map.get("allocation_policy", "balanced"),
        "timezone": s_map.get("timezone", "UTC"),
        "model_version": s_map.get("model_version", "v1.0.0"),
        "model_status": model_status
    }

def update_system_settings(updates: Dict[str, Any]) -> Dict[str, Any]:
    conn = get_db()
    cursor = conn.cursor()
    now = current_iso()
    for k, v in updates.items():
        if v is not None and k in ["allocation_policy", "timezone", "excel_log_path"]:
            cursor.execute("INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)", (k, str(v), now))
    conn.commit()
    conn.close()
    return get_system_settings()

def trigger_excel_rebuild() -> Dict[str, Any]:
    conn = get_db()
    settings = get_system_settings()
    res = rebuild_excel_from_sqlite(conn, settings.get("excel_log_path"))
    conn.close()
    return res
