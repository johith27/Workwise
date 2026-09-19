import re
import json
import logging
from typing import Dict, Any, Optional, List
from backend.service import (
    get_all_employees, get_all_tasks, get_dashboard_summary,
    get_employee_by_id, get_employee_profile, get_task_by_id, generate_recommendation,
    get_all_history_events, get_system_settings, trigger_excel_rebuild,
    create_employee, create_task
)
try:
    # Use groq_client if available (supports both Groq cloud and Ollama local)
    from backend.groq_client import chat_with_gemma, check_ollama_status, OLLAMA_MODEL
except ImportError:
    from backend.ollama_client import chat_with_gemma, check_ollama_status, OLLAMA_MODEL

logger = logging.getLogger("workwise.assistant")

SESSIONS: Dict[str, Dict[str, Any]] = {}

def extract_employee_entities_from_text(text: str) -> Optional[Dict[str, Any]]:
    """
    NLP entity extractor for natural language employee creation requests.
    Supports formats like:
    'Add employee Sarah Connor, email sarah@skynet.com, skills Python:5, Machine Learning:4, location San Francisco, 40 hours'
    'Create worker John Wick, john@wick.com, skills Combat:5, SQL:3, New York'
    """
    lower = text.lower()
    if not any(k in lower for k in ["add employee", "create employee", "register employee", "add worker", "create worker", "new employee"]):
        return None

    # Extract email
    email_match = re.search(r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", text)
    email = email_match.group(1) if email_match else None

    # Extract name
    name = None
    name_match = re.search(r"(?:add|create|register)\s+(?:employee|worker|engineer)?\s*([A-Za-z\s]+?)(?:,\s*email|,\s*skills|,\s*location|,|$)", text, re.IGNORECASE)
    if name_match:
        cand_name = name_match.group(1).strip()
        if cand_name and len(cand_name) > 1 and cand_name.lower() not in ["new", "a", "an", "the"]:
            name = cand_name

    # Extract skills
    skills = "Python:3"
    skills_match = re.search(r"skills?\s*:?\s*([A-Za-z0-9\s:,\-\+]+?)(?:,?\s*location|,?\s*\d+\s*hours?|$)", text, re.IGNORECASE)
    if skills_match:
        sk_str = skills_match.group(1).strip()
        if sk_str and ":" in sk_str:
            skills = sk_str

    # Extract location
    location = "Remote"
    loc_match = re.search(r"locations?\s*:?\s*([A-Za-z\s]+?)(?:,?\s*\d+\s*hours?|$)", text, re.IGNORECASE)
    if loc_match:
        location = loc_match.group(1).strip()

    # Extract hours
    hours = 40.0
    hrs_match = re.search(r"(\d+)\s*(?:hours?|hrs?|h\b)", text, re.IGNORECASE)
    if hrs_match:
        try:
            hours = float(hrs_match.group(1))
        except ValueError:
            pass

    if name and email:
        return {
            "name": name,
            "email": email,
            "skills": skills,
            "location": location,
            "working_hours_per_week": hours,
            "is_active": True,
            "is_available": True
        }
    return None

def extract_task_entities_from_text(text: str) -> Optional[Dict[str, Any]]:
    """
    NLP entity extractor for natural language task creation requests.
    Supports formats like:
    'Create task Build Auth API, effort 10 hours, skills Python:3, priority High'
    """
    lower = text.lower()
    if not re.search(r"(add|create|new)\s+(a\s+)?task", lower):
        return None

    title = None
    estimated_hours = 10.0
    required_skills = "Python:3"
    priority = "Medium"
    location = "Remote"

    title_match = re.search(r"(?:add|create|new)\s+(?:a\s+)?task\s+([A-Za-z0-9\s]+?)(?:,|$|effort|skills|priority)", text, re.IGNORECASE)
    if title_match:
        cand_title = title_match.group(1).strip()
        if cand_title:
            title = cand_title

    hours_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h\b)", text, re.IGNORECASE)
    if hours_match:
        estimated_hours = float(hours_match.group(1))

    skills_match = re.search(r"skills?\s*:?\s*([A-Za-z0-9\s:,\-\+]+?)(?:,|$|priority|effort|location)", text, re.IGNORECASE)
    if skills_match:
        required_skills = skills_match.group(1).strip()

    if "high" in lower:
        priority = "High"
    elif "critical" in lower:
        priority = "Critical"
    elif "low" in lower:
        priority = "Low"

    if title:
        return {
            "title": title,
            "description": "Task created via AI Assistant",
            "required_skills": required_skills,
            "location": location,
            "estimated_hours": estimated_hours,
            "priority": priority,
            "urgency": priority,
            "deadline": None
        }
    return None

def build_system_context() -> str:
    """
    Compiles a comprehensive, real-time snapshot of the database
    to inject into the Gemma 3:4b system prompt.
    """
    try:
        dash = get_dashboard_summary()
        employees = get_all_employees()
        tasks = get_all_tasks()
        settings = get_system_settings()

        emp_summary = []
        for e in employees:
            avail_str = "Available" if e.get("is_available") else "Unavailable"
            emp_summary.append(
                f"- ID #{e['id']} | {e['name']} ({e['email']}) | Location: {e['location']} | "
                f"Skills: [{e['skills']}] | Workload: {e['current_workload']}h/{e['working_hours_per_week']}h "
                f"(Remaining: {e['remaining_capacity']}h) | Status: {avail_str}"
            )

        task_summary = []
        for t in tasks[:15]:
            assigned = t.get("assigned_employee_name") or "Unassigned"
            task_summary.append(
                f"- Task #{t['id']} '{t['title']}' | Status: {t['status']} | Priority: {t['priority']} | "
                f"Required Skills: [{t['required_skills']}] | Effort: {t['estimated_hours']}h | "
                f"Assigned To: {assigned} | Deadline: {t.get('deadline', 'None')}"
            )

        latest_comp = dash.get("latest_completed_task")
        comp_str = "None yet"
        if latest_comp:
            comp_str = f"'{latest_comp.get('title')}' completed by {latest_comp.get('completed_by_employee_name', 'Unassigned')} at {latest_comp.get('completed_at', 'N/A')}"

        context_lines = [
            "### Current Operational Snapshot of WorkWise AI System:",
            f"- Total Employees: {dash.get('total_employees', len(employees))} (Available: {dash.get('available_employees', 0)})",
            f"- Average Capacity Utilization: {dash.get('avg_capacity_utilization', 0.0)}%",
            f"- Tasks: {dash.get('pending_tasks', 0)} Pending, {dash.get('active_tasks', 0)} Active, {dash.get('completed_tasks', 0)} Completed, {dash.get('at_risk_tasks', 0)} At-Risk",
            f"- Latest Completed Task: {comp_str}",
            f"- Shared Excel Mirror Log: {settings.get('excel_log_path', 'N/A')} (Status: {settings.get('excel_sync_status', 'OK')})",
            "\n### Active Workforce Roster:",
            "\n".join(emp_summary) if emp_summary else "No employees registered yet.",
            "\n### Current Tasks Queue:",
            "\n".join(task_summary) if task_summary else "No tasks in queue.",
        ]
        return "\n".join(context_lines)
    except Exception as err:
        logger.error(f"Error generating system context for assistant: {err}")
        return "WorkWise AI operational data could not be retrieved."

def process_assistant_message(message_text: str, session_id: str = "default") -> Dict[str, Any]:
    """
    Processes user messages with the Ollama Gemma 3:4b LLM, augmented with
    live WorkWise AI system context and entity extraction actions.
    """
    text = message_text.strip()
    lower_text = text.lower()
    
    session = SESSIONS.setdefault(session_id, {
        "step": "idle",
        "draft": {},
        "history": []
    })

    # Step 1: Check instant natural language entity extraction & employee creation
    extracted_emp = extract_employee_entities_from_text(text)
    if extracted_emp:
        try:
            emp = create_employee(extracted_emp, actor="AI Assistant (Gemma 3:4b)")
            reply_text = (
                f"🚀 **Employee Profile Successfully Created!**\n\n"
                f"I parsed your request and registered **{emp['name']}** in the WorkWise database:\n\n"
                f"- **Employee ID:** `#{emp['id']}`\n"
                f"- **Email:** `{emp['email']}`\n"
                f"- **Skills:** `{emp['skills']}`\n"
                f"- **Location:** `{emp['location']}`\n"
                f"- **Capacity:** `{emp['working_hours_per_week']}h / week` (Remaining Headroom: `{emp['remaining_capacity']}h`)\n\n"
                f"*This employee is now active and immediately eligible for task allocation and ML recommendation scoring.*"
            )
            session["history"].append({"role": "user", "content": text})
            session["history"].append({"role": "assistant", "content": reply_text})
            return {
                "reply": reply_text,
                "session_id": session_id,
                "action_type": "employee_created",
                "draft_data": emp,
                "model_name": OLLAMA_MODEL,
                "ollama_online": True
            }
        except Exception as e:
            return {
                "reply": f"Could not create employee from prompt: {str(e)}",
                "session_id": session_id,
                "model_name": OLLAMA_MODEL,
                "ollama_online": True
            }

    # Step 1.5: Check instant natural language entity extraction & task creation
    extracted_task = extract_task_entities_from_text(text)
    if extracted_task:
        try:
            task = create_task(extracted_task, actor="AI Assistant")
            reply_text = (
                f"📝 **Task Successfully Created!**\n\n"
                f"I parsed your request and registered the task **{task['title']}**:\n\n"
                f"- **Task ID:** `#{task['id']}`\n"
                f"- **Effort:** `{task['estimated_hours']}h`\n"
                f"- **Skills Required:** `{task['required_skills']}`\n"
                f"- **Priority:** `{task['priority']}`\n\n"
                f"*This task is now in the queue and ready for assignment.*"
            )
            session["history"].append({"role": "user", "content": text})
            session["history"].append({"role": "assistant", "content": reply_text})
            return {
                "reply": reply_text,
                "session_id": session_id,
                "action_type": "task_created",
                "draft_data": task,
                "model_name": OLLAMA_MODEL,
                "ollama_online": True
            }
        except Exception as e:
            return {
                "reply": f"Could not create task from prompt: {str(e)}",
                "session_id": session_id,
                "model_name": OLLAMA_MODEL,
                "ollama_online": True
            }

    # Step 2: Assemble System Prompt with live DB Context for Gemma 3:4b
    system_context = build_system_context()
    system_prompt = (
        "You are WorkWise AI Assistant, an expert workforce operations and resource allocation agent "
        f"powered by the local '{OLLAMA_MODEL}' LLM.\n\n"
        "Your role is to help project managers allocate resources, match skilled engineers to tasks, "
        "monitor workload capacity, prevent burnout, resolve at-risk tasks, and audit allocation history.\n\n"
        "Use the following LIVE SYSTEM DATA snapshot from SQLite to answer questions accurately and authoritatively:\n\n"
        f"{system_context}\n\n"
        "INSTRUCTIONS:\n"
        "1. Reference specific employee names, IDs, skills, and exact workload/capacity numbers from the live data whenever relevant.\n"
        "2. Format your response cleanly with Markdown (bullet points, bold key facts, backticks for IDs/skills).\n"
        "3. If asked who is best for a task or skill, evaluate their required skill proficiency vs employee skill level and current remaining capacity.\n"
        "4. Keep your responses crisp, direct, and actionable."
    )

    # Maintain recent session history (last 8 turns to keep context fast and compact)
    chat_history: List[Dict[str, str]] = session.get("history", [])[-8:]
    chat_history.append({"role": "user", "content": text})

    # Step 3: Query Ollama Gemma 3:4b
    status_info = check_ollama_status()
    if status_info.get("online"):
        llm_reply = chat_with_gemma(chat_history, system_prompt=system_prompt, temperature=0.3)
        # Store back in session history
        session["history"].append({"role": "user", "content": text})
        session["history"].append({"role": "assistant", "content": llm_reply})

        return {
            "reply": llm_reply,
            "session_id": session_id,
            "model_name": OLLAMA_MODEL,
            "ollama_online": True
        }

    # Fallback if Ollama is not running
    logger.warning("Ollama not reachable; providing rule-based response fallback.")
    fallback_reply = (
        "⚠️ **Ollama (Gemma 3:4b) is currently offline.**\n\n"
        "To enable full generative AI reasoning, start Ollama with:\n"
        "```bash\nollama run gemma3:4b\n```\n\n"
        "Here is the current live system snapshot:\n\n"
    )

    # Basic rule-based fallback
    if "employee" in lower_text:
        emps = get_all_employees()
        fallback_reply += f"**Active Employees ({len(emps)}):**\n"
        for e in emps:
            fallback_reply += f"- **{e['name']}** (#{e['id']}): Skills `{e['skills']}`, Capacity `{e['remaining_capacity']}h` remaining\n"
    elif "task" in lower_text:
        tasks = get_all_tasks()
        fallback_reply += f"**Current Tasks ({len(tasks)}):**\n"
        for t in tasks[:5]:
            fallback_reply += f"- **{t['title']}** (#{t['id']}): Status `{t['status']}`, Priority `{t['priority']}`\n"
    else:
        fallback_reply += "You can ask about available employees, pending tasks, workload capacity, or say: *'Add employee Sarah Connor, email sarah@skynet.com, skills Python:5, location San Francisco, 40 hours'*."

    return {
        "reply": fallback_reply,
        "session_id": session_id,
        "model_name": OLLAMA_MODEL,
        "ollama_online": False
    }
