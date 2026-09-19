# START HERE — Beginner Guide for Running WorkWise AI

Welcome to **WorkWise AI**! Follow this simple step-by-step guide to run the project and perform the full hackathon demonstration flow on Windows.

---

## 🚀 Step-by-Step Setup

### Step 1: Open PowerShell in the project directory
Open PowerShell and navigate to the project directory:
```powershell
cd C:\Users\lsind\.gemini\antigravity\scratch\workwise_app
```

### Step 2: Run the automated launcher
Double click `run.bat` or execute in PowerShell:
```powershell
.\run.bat
```
`run.bat` will automatically:
1. Create a Python virtual environment (`.venv`)
2. Install all required dependencies from `requirements-dev.txt`
3. Initialize the SQLite database at `data/workwise.db`
4. Train the Random Forest ML candidate ranking model at `models/workforce_random_forest.pkl`
5. Verify the React production build in `frontend/dist`
6. Start the web server at `http://127.0.0.1:8000`

---

## 🎬 10-Step Hackathon Demo Script

1. **Open Dashboard**: Go to `http://127.0.0.1:8000` in your web browser.
2. **Add Employees**: Click the **Employees** tab -> **Add Employee**. Create two employees:
   - *Alice*: Skills `Python:4,FastAPI:3`, Location `New York`, Hours `40`
   - *Bob*: Skills `Python:2`, Location `London`, Hours `40`
3. **Create Task**: Click the **Tasks** tab -> **Create Task**:
   - Title: `Build Auth API`, Required Skills: `Python:3,FastAPI:3`, Effort: `15h`, Location: `New York`
4. **Generate Recommendation**: Click **Match** on the task or open the **Recommendations** tab.
5. **Inspect Hard Constraints & ML Score**:
   - Notice *Alice* passed all hard constraints with a top Random Forest score (e.g., 99.9%).
   - Notice *Bob* failed hard constraints due to skill level gap (`Python:2` vs required `Python:3`).
6. **Approve Allocation**: Click **Approve** for Alice.
7. **Open Shared Excel Log**: Open `data/history/allocation_history.xlsx` in Excel.
   - Verify row `EVT-...` with `event_type = approved`, `employee_name = Alice`, and all 23 columns populated!
8. **Test Dynamic Reallocation**:
   - On the **Employees** tab, toggle Alice's status to **Set Unavailable**.
   - Notice the task `Build Auth API` is immediately flagged **AT-RISK** on the Dashboard, and a replacement recommendation cycle is generated automatically!
9. **Complete Task**:
   - Re-enable Alice's availability and click **Complete** on the task.
   - Notice Alice's remaining capacity returns to 40h on both the Dashboard and Excel log.
10. **Test AI Assistant**:
   - Open the **AI Assistant** tab and ask: `"Who completed the latest task?"` or `"Show allocation history"`.
