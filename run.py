import os
import sys
import subprocess
import uvicorn
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

def check_and_setup_environment():
    print("==========================================================================")
    print("  WorkWise AI — Workforce Decision & Resource Allocation Agent Startup  ")
    print("==========================================================================")

    # 1. Initialize SQLite Database Schema
    from backend.db import init_db
    print("[1/3] Initializing operational SQLite database schema...")
    init_db()
    print("      Database ready at data/workwise.db")

    # 2. Check & Train ML Model
    model_path = BASE_DIR / "models" / "workforce_random_forest.pkl"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    if not model_path.exists():
        print("[2/3] Random Forest ML model not found. Training model now...")
        from training.train_model import train_and_save_model
        train_and_save_model()
    else:
        print("[2/3] Random Forest ML model verified at models/workforce_random_forest.pkl")

    # 3. Verify Frontend Build
    dist_path = BASE_DIR / "frontend" / "dist"
    if not dist_path.exists():
        print("[3/3] Frontend production build missing at frontend/dist. Building now...")
        try:
            node_cmd = r"C:\PROGRA~1\nodejs\node.exe" if Path(r"C:\PROGRA~1\nodejs\node.exe").exists() else "node"
            npm_cli = r"C:\PROGRA~1\nodejs\node_modules\npm\bin\npm-cli.js"
            if Path(npm_cli).exists():
                subprocess.run([node_cmd, npm_cli, "install", "--ignore-scripts"], cwd=str(BASE_DIR / "frontend"), check=True)
                subprocess.run([node_cmd, "node_modules/vite/bin/vite.js", "build"], cwd=str(BASE_DIR / "frontend"), check=True)
            else:
                subprocess.run(["npm", "run", "build"], cwd=str(BASE_DIR / "frontend"), check=True, shell=True)
            print("      Frontend build complete.")
        except Exception as e:
            print(f"      Warning: Automatic frontend build step failed ({e}). Backend will run API endpoints.")
    else:
        print("[3/3] Frontend production assets verified at frontend/dist")

    print("\nStarting WorkWise AI Web Server & REST API...")
    print("App Dashboard:  http://127.0.0.1:8000")
    print("API Specs:      http://127.0.0.1:8000/docs")
    print("Press Ctrl+C to stop.\n")

if __name__ == "__main__":
    check_and_setup_environment()
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=False)
