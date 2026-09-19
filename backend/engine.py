import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import joblib
import numpy as np
import pandas as pd

logger = logging.getLogger("workwise.engine")

MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "workforce_random_forest.pkl"
MANIFEST_PATH = Path(__file__).resolve().parent.parent / "models" / "model_manifest.json"

PRIORITY_WEIGHTS = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}
URGENCY_WEIGHTS = {"Urgent": 4, "High": 3, "Medium": 2, "Low": 1}

FEATURE_NAMES = [
    "skill_match_ratio",
    "skill_level_surplus",
    "workload_ratio",
    "capacity_headroom",
    "location_match",
    "historical_success_rate",
    "estimated_hours",
    "priority_num"
]

def parse_skills(skills_str: str) -> Dict[str, int]:
    if not skills_str:
        return {}
    skills_str = skills_str.strip()
    if skills_str.startswith("{"):
        try:
            return {k.strip(): int(v) for k, v in json.loads(skills_str).items()}
        except Exception:
            pass
    res = {}
    for part in skills_str.split(","):
        if ":" in part:
            name, level = part.split(":", 1)
            try:
                res[name.strip()] = int(level.strip())
            except ValueError:
                res[name.strip()] = 1
        elif part.strip():
            res[part.strip()] = 1
    return res

def calculate_priority_score(task_dict: Dict[str, Any]) -> float:
    p_wt = PRIORITY_WEIGHTS.get(task_dict.get("priority", "Medium"), 2)
    u_wt = URGENCY_WEIGHTS.get(task_dict.get("urgency", "Medium"), 2)
    
    deadline_str = task_dict.get("deadline", "")
    hours_to_deadline = 1000.0
    if deadline_str:
        try:
            deadline_dt = datetime.fromisoformat(deadline_str.replace("Z", "+00:00"))
            now_dt = datetime.now(deadline_dt.tzinfo) if deadline_dt.tzinfo else datetime.now()
            diff_hours = (deadline_dt - now_dt).total_seconds() / 3600.0
            hours_to_deadline = max(0.1, diff_hours)
        except Exception:
            pass
    
    deadline_score = 100.0 / (hours_to_deadline + 1.0)
    return (p_wt * 10.0) + (u_wt * 5.0) + deadline_score

def evaluate_hard_constraints(
    task: Dict[str, Any],
    employee: Dict[str, Any],
    employee_current_workload: float
) -> Tuple[bool, Dict[str, Any], str]:
    failures = []
    details = {
        "active_available": True,
        "skills_match": True,
        "location_match": True,
        "capacity_available": True,
        "missing_skills": [],
        "capacity_headroom": 0.0
    }

    if not employee.get("is_active", True):
        failures.append("Employee is deactivated")
        details["active_available"] = False
    elif not employee.get("is_available", True):
        failures.append("Employee is marked temporarily unavailable")
        details["active_available"] = False

    req_skills = parse_skills(task.get("required_skills", ""))
    emp_skills = parse_skills(employee.get("skills", ""))
    missing_or_insufficient = []

    for req_skill, req_level in req_skills.items():
        emp_level = emp_skills.get(req_skill, 0)
        if emp_level < req_level:
            missing_or_insufficient.append(f"{req_skill} (required level {req_level}, candidate has {emp_level})")

    if missing_or_insufficient:
        failures.append(f"Skill gaps: {'; '.join(missing_or_insufficient)}")
        details["skills_match"] = False
        details["missing_skills"] = missing_or_insufficient

    task_loc = (task.get("location") or "").strip().lower()
    emp_loc = (employee.get("location") or "").strip().lower()
    if task_loc and task_loc not in ["remote", "any", "all"] and emp_loc not in ["remote", "any", "all"]:
        if task_loc != emp_loc:
            failures.append(f"Location mismatch: task requires '{task.get('location')}', candidate is in '{employee.get('location')}'")
            details["location_match"] = False

    weekly_hours = float(employee.get("working_hours_per_week", 40.0))
    rem_capacity = weekly_hours - employee_current_workload
    estimated_hours = float(task.get("estimated_hours", 0.0))
    details["capacity_headroom"] = rem_capacity - estimated_hours

    if rem_capacity < estimated_hours:
        failures.append(f"Insufficient capacity: task requires {estimated_hours}h, candidate has {max(0.0, rem_capacity):.1f}h remaining")
        details["capacity_available"] = False

    passed = len(failures) == 0
    reason_summary = "All hard constraints passed" if passed else " | ".join(failures)
    return passed, details, reason_summary

def extract_features(
    task: Dict[str, Any],
    employee: Dict[str, Any],
    employee_current_workload: float,
    historical_success_rate: float = 1.0
) -> List[float]:
    req_skills = parse_skills(task.get("required_skills", ""))
    emp_skills = parse_skills(employee.get("skills", ""))
    
    if req_skills:
        matched_count = sum(1 for k, v in req_skills.items() if emp_skills.get(k, 0) >= v)
        skill_match_ratio = matched_count / float(len(req_skills))
        surplus_list = [emp_skills.get(k, 0) - v for k, v in req_skills.items()]
        skill_level_surplus = float(np.mean(surplus_list))
    else:
        skill_match_ratio = 1.0
        skill_level_surplus = 0.0

    weekly_hours = float(employee.get("working_hours_per_week", 40.0))
    workload_ratio = float(employee_current_workload) / max(1.0, weekly_hours)
    capacity_headroom = weekly_hours - employee_current_workload - float(task.get("estimated_hours", 0.0))

    task_loc = (task.get("location") or "").strip().lower()
    emp_loc = (employee.get("location") or "").strip().lower()
    location_match = 1.0 if (not task_loc or task_loc in ["remote", "any"] or emp_loc in ["remote", "any"] or task_loc == emp_loc) else 0.0
    
    priority_num = float(PRIORITY_WEIGHTS.get(task.get("priority", "Medium"), 2))
    estimated_hours = float(task.get("estimated_hours", 0.0))

    return [
        skill_match_ratio,
        skill_level_surplus,
        workload_ratio,
        capacity_headroom,
        location_match,
        float(historical_success_rate),
        estimated_hours,
        priority_num
    ]

def predict_candidate_rankings(
    task: Dict[str, Any],
    candidates: List[Dict[str, Any]],
    workload_map: Dict[int, float],
    historical_rates_map: Dict[int, float]
) -> Tuple[List[Dict[str, Any]], str]:
    model = None
    manifest = None
    model_version = "MODEL_NOT_CONFIGURED"

    if MODEL_PATH.exists() and MANIFEST_PATH.exists():
        try:
            model = joblib.load(MODEL_PATH)
            with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            model_version = manifest.get("model_version", "v1.0.0")
        except Exception as e:
            logger.warning(f"Failed to load ML model: {e}")
            model = None

    evaluated_candidates = []

    for emp in candidates:
        emp_id = emp["id"]
        current_workload = workload_map.get(emp_id, 0.0)
        hist_rate = historical_rates_map.get(emp_id, 1.0)
        
        passed, constraint_details, constraint_summary = evaluate_hard_constraints(
            task, emp, current_workload
        )

        features = extract_features(task, emp, current_workload, hist_rate)

        score = 0.0
        if model is not None:
            try:
                X_df = pd.DataFrame([features], columns=FEATURE_NAMES)
                if hasattr(model, "predict_proba"):
                    score = float(model.predict_proba(X_df)[0][1])
                else:
                    score = float(model.predict(X_df)[0])
            except Exception as e:
                logger.warning(f"Prediction error for candidate {emp_id}: {e}")
                score = _compute_heuristic_score(features)
        else:
            score = _compute_heuristic_score(features)

        weekly_hours = float(emp.get("working_hours_per_week", 40.0))
        rem_cap = max(0.0, weekly_hours - current_workload)

        evaluated_candidates.append({
            "employee_id": emp_id,
            "employee_name": emp["name"],
            "score": round(score, 4),
            "hard_constraints_passed": passed,
            "constraint_details": constraint_details,
            "rejection_reason": None if passed else constraint_summary,
            "employee_current_workload": current_workload,
            "employee_remaining_capacity": rem_cap
        })

    evaluated_candidates.sort(
        key=lambda c: (1 if c["hard_constraints_passed"] else 0, c["score"]),
        reverse=True
    )

    for rank_idx, cand in enumerate(evaluated_candidates, 1):
        cand["rank"] = rank_idx

    return evaluated_candidates, model_version

def _compute_heuristic_score(features: List[float]) -> float:
    skill_match_ratio = features[0]
    skill_level_surplus = features[1]
    workload_ratio = features[2]
    capacity_headroom = features[3]
    location_match = features[4]
    historical_success_rate = features[5]

    base = (skill_match_ratio * 0.4) + (min(1.0, max(0.0, 1.0 - workload_ratio)) * 0.3) + (historical_success_rate * 0.2) + (location_match * 0.1)
    surplus_bonus = min(0.2, max(-0.2, skill_level_surplus * 0.05))
    return float(np.clip(base + surplus_bonus, 0.0, 1.0))
