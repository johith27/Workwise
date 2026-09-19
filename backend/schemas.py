from typing import List, Optional, Dict, Any
from pydantic import BaseModel, EmailStr, Field

class SkillProficiency(BaseModel):
    skill: str
    level: int = Field(ge=1, le=5, description="Proficiency level from 1 to 5")

# Employee Schemas
class EmployeeBase(BaseModel):
    name: str
    email: str
    skills: str  # Format: "Python:4,FastAPI:3" or JSON string
    location: str
    working_hours_per_week: float = 40.0
    working_window_start: str = "09:00"
    working_window_end: str = "17:00"
    timezone: str = "UTC"
    is_active: bool = True
    is_available: bool = True

class EmployeeCreate(EmployeeBase):
    pass

class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    skills: Optional[str] = None
    location: Optional[str] = None
    working_hours_per_week: Optional[float] = None
    working_window_start: Optional[str] = None
    working_window_end: Optional[str] = None
    timezone: Optional[str] = None
    is_active: Optional[bool] = None
    is_available: Optional[bool] = None

class EmployeeResponse(EmployeeBase):
    id: int
    current_workload: float = 0.0
    remaining_capacity: float = 40.0
    active_assignments_count: int = 0
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True

# Task Schemas
class TaskBase(BaseModel):
    title: str
    description: str = ""
    required_skills: str  # Format: "Python:3"
    location: str = ""
    estimated_hours: float
    priority: str = "Medium"  # Low, Medium, High, Critical
    urgency: str = "Medium"   # Low, Medium, High, Urgent
    deadline: str
    sla_hours: float = 24.0

class TaskCreate(TaskBase):
    pass

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    required_skills: Optional[str] = None
    location: Optional[str] = None
    estimated_hours: Optional[float] = None
    priority: Optional[str] = None
    urgency: Optional[str] = None
    deadline: Optional[str] = None
    sla_hours: Optional[float] = None
    status: Optional[str] = None

class TaskResponse(TaskBase):
    id: int
    status: str
    assigned_employee_id: Optional[int] = None
    assigned_employee_name: Optional[str] = None
    assigned_at: Optional[str] = None
    completed_at: Optional[str] = None
    completed_by_employee_id: Optional[int] = None
    completed_by_employee_name: Optional[str] = None
    completed_by_actor: Optional[str] = None
    is_at_risk: bool = False
    at_risk_reason: Optional[str] = None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True

# Candidate Recommendation Schemas
class CandidateDetail(BaseModel):
    employee_id: int
    employee_name: str
    rank: int
    score: float
    hard_constraints_passed: bool
    constraint_details: Dict[str, Any]
    status: str = "pending"
    rejection_reason: Optional[str] = None
    employee_current_workload: float = 0.0
    employee_remaining_capacity: float = 40.0

class RecommendationCycleResponse(BaseModel):
    cycle_id: int
    task_id: int
    task_title: str
    created_at: str
    status: str
    model_version: str
    trigger_reason: str
    candidates: List[CandidateDetail]
    no_qualifying_reason: Optional[str] = None

class ApproveRejectRequest(BaseModel):
    actor: str = "Manager"
    reason: Optional[str] = None

# History Schemas
class HistoryEventResponse(BaseModel):
    id: int
    event_id: str
    event_type: str
    task_id: Optional[int] = None
    task_title: Optional[str] = None
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    previous_employee_id: Optional[int] = None
    previous_employee_name: Optional[str] = None
    priority: Optional[str] = None
    urgency: Optional[str] = None
    deadline: Optional[str] = None
    sla: Optional[str] = None
    location: Optional[str] = None
    estimated_hours: Optional[float] = None
    remaining_hours_before: Optional[float] = None
    remaining_hours_after: Optional[float] = None
    matching_score_or_rank: Optional[str] = None
    constraint_checks: Optional[str] = None
    trigger_reason: Optional[str] = None
    actor: str
    timestamp: str
    model_version: Optional[str] = None
    notes: Optional[str] = None

# Employee Profile Schema
class EmployeeProfileResponse(BaseModel):
    employee: EmployeeResponse
    active_assignments: List[Dict[str, Any]]
    completed_assignments_count: int
    total_hours_delivered: float
    assignment_history: List[Dict[str, Any]]
    audit_history: List[HistoryEventResponse]

# Dashboard Schemas
class DashboardResponse(BaseModel):
    total_employees: int
    available_employees: int
    pending_tasks: int
    active_tasks: int
    completed_tasks: int
    at_risk_tasks: int
    avg_capacity_utilization: float
    pending_recommendations: List[RecommendationCycleResponse]
    at_risk_task_list: List[TaskResponse]
    recent_activity: List[HistoryEventResponse]
    latest_completed_task: Optional[TaskResponse] = None
    latest_completed_employee: Optional[EmployeeResponse] = None

# Settings Schemas
class SettingsResponse(BaseModel):
    excel_log_path: str
    last_excel_sync: str
    excel_sync_status: str
    excel_row_count: int
    allocation_policy: str
    timezone: str
    model_version: str
    model_status: str

class SettingsUpdate(BaseModel):
    allocation_policy: Optional[str] = None
    timezone: Optional[str] = None
    excel_log_path: Optional[str] = None

# Assistant Schemas
class AssistantMessageRequest(BaseModel):
    message: str
    session_id: str = "default"

class AssistantMessageResponse(BaseModel):
    reply: str
    session_id: str
    action_type: Optional[str] = None
    draft_data: Optional[Dict[str, Any]] = None
    model_name: Optional[str] = "gemma3:4b"
    ollama_online: Optional[bool] = True

class AssistantStatusResponse(BaseModel):
    online: bool
    model: str
    model_available: bool
    status: str
    base_url: str

# CSV Import Schemas
class ImportPreviewResponse(BaseModel):
    import_id: int
    filename: str
    file_type: str
    total_rows: int
    valid_rows: int
    invalid_rows: int
    errors: List[Dict[str, Any]]
    preview_data: List[Dict[str, Any]]

class ImportConfirmRequest(BaseModel):
    actor: str = "Manager"
