import os
import io
import csv
import logging
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from backend.db import init_db, get_db
from backend.schemas import (
    EmployeeCreate, EmployeeUpdate, EmployeeResponse, EmployeeProfileResponse,
    TaskCreate, TaskUpdate, TaskResponse,
    RecommendationCycleResponse, ApproveRejectRequest,
    DashboardResponse, SettingsResponse, SettingsUpdate,
    AssistantMessageRequest, AssistantMessageResponse, AssistantStatusResponse,
    ImportConfirmRequest, HistoryEventResponse
)
from backend.service import (
    get_all_employees, get_employee_by_id, get_employee_profile, create_employee, update_employee,
    get_all_tasks, get_task_by_id, create_task, update_task, complete_task, cancel_task,
    generate_recommendation, get_recommendation_cycle_by_id, get_all_pending_recommendations,
    approve_candidate, reject_candidate, get_dashboard_summary, get_all_history_events,
    get_system_settings, update_system_settings, trigger_excel_rebuild
)
from backend.imports import parse_and_validate_csv, process_csv_import
from backend.assistant import process_assistant_message
try:
    from backend.groq_client import check_ollama_status
except ImportError:
    from backend.ollama_client import check_ollama_status

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("workwise.main")

app = FastAPI(
    title="WorkWise AI — Workforce Decision & Resource Allocation API",
    version="1.0.0",
    description="API for mAI-04 AI Workforce Decision & Resource Allocation Agent"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    init_db()
    logger.info("WorkWise AI API initialized.")

# Employee Routes
@app.get("/api/employees", response_model=List[EmployeeResponse])
def list_employees_endpoint(
    search: Optional[str] = None,
    skill: Optional[str] = None,
    is_active: Optional[bool] = None
):
    return get_all_employees(search=search, skill_filter=skill, is_active=is_active)

@app.get("/api/employees/{employee_id}", response_model=EmployeeResponse)
def get_employee_endpoint(employee_id: int):
    emp = get_employee_by_id(employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    return emp

@app.get("/api/employees/{employee_id}/profile", response_model=EmployeeProfileResponse)
def get_employee_profile_endpoint(employee_id: int):
    prof = get_employee_profile(employee_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Employee profile not found")
    return prof

@app.post("/api/employees", response_model=EmployeeResponse)
def create_employee_endpoint(payload: EmployeeCreate):
    try:
        return create_employee(payload.dict(), actor="Manager")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.patch("/api/employees/{employee_id}", response_model=EmployeeResponse)
def update_employee_endpoint(employee_id: int, payload: EmployeeUpdate):
    emp = update_employee(employee_id, payload.dict(exclude_unset=True), actor="Manager")
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    return emp

@app.post("/api/employees/{employee_id}/deactivate", response_model=EmployeeResponse)
def deactivate_employee_endpoint(employee_id: int):
    emp = update_employee(employee_id, {"is_active": False, "is_available": False}, actor="Manager")
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    return emp

@app.post("/api/employees/{employee_id}/restore", response_model=EmployeeResponse)
def restore_employee_endpoint(employee_id: int):
    emp = update_employee(employee_id, {"is_active": True, "is_available": True}, actor="Manager")
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    return emp

# Task Routes
@app.get("/api/tasks", response_model=List[TaskResponse])
def list_tasks_endpoint(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    search: Optional[str] = None
):
    return get_all_tasks(status=status, priority=priority, search=search)

@app.get("/api/tasks/{task_id}", response_model=TaskResponse)
def get_task_endpoint(task_id: int):
    task = get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@app.post("/api/tasks", response_model=TaskResponse)
def create_task_endpoint(payload: TaskCreate):
    try:
        return create_task(payload.dict(), actor="Manager")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.patch("/api/tasks/{task_id}", response_model=TaskResponse)
def update_task_endpoint(task_id: int, payload: TaskUpdate):
    task = update_task(task_id, payload.dict(exclude_unset=True), actor="Manager")
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@app.post("/api/tasks/{task_id}/recommend", response_model=RecommendationCycleResponse)
def recommend_task_endpoint(task_id: int, trigger_reason: str = "manual_request"):
    try:
        return generate_recommendation(task_id, trigger_reason=trigger_reason, actor="Manager")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/tasks/{task_id}/complete", response_model=TaskResponse)
def complete_task_endpoint(task_id: int, actor: str = "Manager", employee_id: Optional[int] = None):
    task = complete_task(task_id, actor=actor, employee_id=employee_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@app.post("/api/tasks/{task_id}/cancel", response_model=TaskResponse)
def cancel_task_endpoint(task_id: int, actor: str = "Manager", reason: str = "Cancelled by user"):
    task = cancel_task(task_id, actor=actor, reason=reason)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

# Recommendation Routes
@app.get("/api/recommendations", response_model=List[RecommendationCycleResponse])
def list_recommendations_endpoint():
    return get_all_pending_recommendations()

@app.get("/api/recommendations/{cycle_id}", response_model=RecommendationCycleResponse)
def get_recommendation_endpoint(cycle_id: int):
    try:
        return get_recommendation_cycle_by_id(cycle_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/api/recommendations/{cycle_id}/approve", response_model=RecommendationCycleResponse)
def approve_recommendation_endpoint(cycle_id: int, candidate_employee_id: int = Query(...), payload: Optional[ApproveRejectRequest] = None):
    actor = payload.actor if payload else "Manager"
    reason = payload.reason if payload else None
    try:
        return approve_candidate(cycle_id, candidate_employee_id, actor=actor, reason=reason)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/recommendations/{cycle_id}/reject", response_model=RecommendationCycleResponse)
def reject_recommendation_endpoint(cycle_id: int, candidate_employee_id: int = Query(...), payload: Optional[ApproveRejectRequest] = None):
    actor = payload.actor if payload else "Manager"
    reason = payload.reason if payload else None
    try:
        return reject_candidate(cycle_id, candidate_employee_id, actor=actor, reason=reason)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Dashboard Route
@app.get("/api/dashboard", response_model=DashboardResponse)
def get_dashboard_endpoint():
    return get_dashboard_summary()

# History Routes
@app.get("/api/history", response_model=List[HistoryEventResponse])
def get_history_endpoint(
    employee_id: Optional[int] = None,
    task_id: Optional[int] = None,
    event_type: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100
):
    return get_all_history_events(
        employee_id=employee_id, task_id=task_id, event_type=event_type, search=search, limit=limit
    )

@app.get("/api/history/export")
def export_history_endpoint(format: str = Query("csv", regex="^(csv|xlsx)$")):
    events = get_all_history_events(limit=5000)
    
    if format == "xlsx":
        # Stream the shared Excel workbook file
        settings = get_system_settings()
        excel_path = Path(settings["excel_log_path"])
        if not excel_path.exists():
            trigger_excel_rebuild()
        return FileResponse(
            path=str(excel_path),
            filename="allocation_history.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    # Default CSV streaming
    output = io.StringIO()
    writer = csv.writer(output)
    headers = [
        "event_id", "event_type", "task_id", "task_title", "employee_id", "employee_name",
        "previous_employee_id", "previous_employee_name", "priority", "urgency", "deadline",
        "sla", "location", "estimated_hours", "remaining_hours_before", "remaining_hours_after",
        "matching_score_or_rank", "constraint_checks", "trigger_reason", "actor", "timestamp",
        "model_version", "notes"
    ]
    writer.writerow(headers)
    for ev in events:
        writer.writerow([ev.get(h, "") for h in headers])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=allocation_history.csv"}
    )

@app.post("/api/history/rebuild-excel")
def rebuild_excel_endpoint():
    try:
        return trigger_excel_rebuild()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Settings Routes
@app.get("/api/settings", response_model=SettingsResponse)
def get_settings_endpoint():
    return get_system_settings()

@app.patch("/api/settings", response_model=SettingsResponse)
def update_settings_endpoint(payload: SettingsUpdate):
    return update_system_settings(payload.dict(exclude_unset=True))

# CSV Import Routes
@app.post("/api/imports/preview")
async def preview_csv_import(
    file: UploadFile = File(...),
    file_type: str = Form(...)  # employees, tasks, events
):
    content = await file.read()
    summary, valid_rows, errors = parse_and_validate_csv(content, file_type, file.filename)
    return {
        "summary": summary,
        "valid_rows": valid_rows,
        "errors": errors
    }

@app.post("/api/imports/confirm")
async def confirm_csv_import(
    file: UploadFile = File(...),
    file_type: str = Form(...),
    actor: str = Form("Manager")
):
    content = await file.read()
    return process_csv_import(content, file_type, file.filename, actor=actor)

# AI Assistant Route
@app.post("/api/assistant/message", response_model=AssistantMessageResponse)
def assistant_message_endpoint(payload: AssistantMessageRequest):
    return process_assistant_message(payload.message, session_id=payload.session_id)

@app.get("/api/assistant/status", response_model=AssistantStatusResponse)
def assistant_status_endpoint():
    return check_ollama_status()

# Serve Frontend Static Assets if available
DIST_PATH = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if DIST_PATH.exists():
    app.mount("/assets", StaticFiles(directory=str(DIST_PATH / "assets")), name="assets")

    @app.get("/{full_path:path}")
    def serve_frontend_spa(full_path: str):
        if full_path.startswith("api"):
            raise HTTPException(status_code=404, detail="API route not found")
        file_target = DIST_PATH / full_path
        if file_target.exists() and file_target.is_file():
            return FileResponse(file_target)
        return FileResponse(DIST_PATH / "index.html")
