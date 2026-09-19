# WorkWise AI — AI Workforce Decision & Resource Allocation Agent

**WorkWise AI** is a complete, dynamic workforce allocation and decision system built for hackathon problem statement **mAI-04**. It continuously monitors employee workload, task priorities, SLAs, deadlines, skill proficiencies, and availability to perform dynamic resource reallocation rather than static assignments.

---

## Key Features

1. **Dynamic Reallocation Engine**:
   - Priority queue based on priority weight, urgency, deadline, and waiting time.
   - Hard constraint filtering: active/available status, skill proficiency match, location match, working window, capacity limits (`current_workload + estimated_hours <= capacity`), deadline buffer.
   - Machine Learning candidate suitability scoring via Scikit-learn **Random Forest**.
   - Clear diagnostic failure explanations when no candidate qualifies.

2. **Dual-Persistence Architecture**:
   - **SQLite (`data/workwise.db`)**: System of record enforcing ACID transactions, foreign keys, and concurrency safety.
   - **Shared Excel Log (`data/history/allocation_history.xlsx`)**: Read-and-share friendly audit workbook updated on EVERY allocation event via `backend/excel_sync.py` in append mode. All 23 required columns populated.
   - **Reconciliation Engine**: One-click rebuild to recover or sync the Excel workbook from SQLite.

3. **Multi-Channel AI Assistant**:
   - Interactive conversational UI supporting queries ("Show available employees", "Who completed the latest task?").
   - Multi-step guided entity creation with draft previews and user confirmation.
   - Reuses identical backend business service functions as the React dashboard.

4. **CSV Bulk Data Imports**:
   - Templates for `employees`, `tasks`, and `events`.
   - Pre-import validation, duplicate detection, row-level error reporting, preview, and transactional persistence to SQLite and Excel.

---

## Tech Stack

- **Backend**: Python 3.13, FastAPI 0.141.1, Pydantic 2.13.5, SQLite3, Uvicorn
- **ML & Data**: scikit-learn 1.8.0 (Random Forest), pandas 2.2.3, NumPy 2.3.5, joblib 1.5.3, openpyxl 3.1.5
- **Frontend**: React 19, Vite 6, Lucide React icons, CSS
- **Testing**: pytest 9.1.1, httpx 0.28.1

---

## Fast Start Instructions (Windows PowerShell)

```powershell
# 1. Clone/Navigate to folder
cd workwise_app

# 2. Setup Virtual Environment & Install Dependencies
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt

# 3. Train Machine Learning Model & Run Test Suite
.\.venv\Scripts\python.exe training/train_model.py
.\.venv\Scripts\python.exe -m pytest -v

# 4. Launch Application
.\.venv\Scripts\python.exe run.py
```

- **Dashboard**: `http://127.0.0.1:8000`
- **Swagger API Specs**: `http://127.0.0.1:8000/docs`
