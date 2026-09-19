# WorkWise AI — Filename & Code Guide

This reference document outlines every file, module, and purpose in the **WorkWise AI** codebase.

```
workwise_app/
├── run.py                              # Main Python launcher & environment setup script
├── run.bat                             # Windows batch file for 1-click execution
├── requirements.txt                    # Production dependencies (FastAPI, scikit-learn, openpyxl, pandas)
├── requirements-dev.txt                # Development dependencies (pytest, httpx)
├── README.md                           # Technical overview & architecture documentation
├── START_HERE.md                       # Beginner-friendly quick start & 10-step demo script
├── WorkWise_AI_Filename_Code_Guide.md  # Detailed code & directory reference guide
│
├── backend/                            # FastAPI Backend Engine
│   ├── __init__.py                     # Package init
│   ├── main.py                         # FastAPI routes, static file serving, CORS
│   ├── db.py                           # SQLite schema initialization & foreign key setup
│   ├── schemas.py                      # Pydantic request/response validation schemas
│   ├── service.py                      # Central business logic (workload, approval, completion, reallocation)
│   ├── engine.py                       # Hard constraint filter & Random Forest candidate ranking
│   ├── assistant.py                    # Guided AI Assistant NLP parser & command processor
│   ├── imports.py                      # CSV validation, preview, duplicate detection, and import
│   └── excel_sync.py                   # Thread-safe openpyxl shared log synchronizer & SQLite rebuild engine
│
├── frontend/                           # React + Vite Dashboard
│   ├── package.json                    # Node dependencies (React 19, Lucide icons, Vite 6)
│   ├── vite.config.js                  # Vite bundler & API proxy configuration
│   ├── index.html                      # HTML root template
│   └── src/
│       ├── main.jsx                    # React app entry point
│       ├── App.jsx                     # Dashboard UI, modal popups, chat window, data tables
│       └── styles.css                  # Custom CSS styles, themes, badges, responsive layout
│
├── training/                           # Machine Learning Training Pipeline
│   ├── __init__.py                     # Package init
│   ├── train_model.py                  # Random Forest model trainer & metric reporter
│   └── train_intents.py                # Intent classifier helper
│
├── models/                             # Trained Artifacts
│   ├── workforce_random_forest.pkl     # Serialized Scikit-learn Random Forest model
│   └── model_manifest.json             # Model metadata, versioning, feature order, evaluation metrics
│
├── templates/                          # CSV Import Templates
│   ├── employees_template.csv          # Template header & sample rows for employees
│   ├── tasks_template.csv              # Template header & sample rows for tasks
│   └── events_template.csv             # Template header & sample rows for audit events
│
├── tests/                              # Automated Test Suite
│   ├── __init__.py                     # Package init
│   ├── test_workflows.py               # End-to-end task lifecycle, capacity math, reallocation tests
│   ├── test_training.py                # ML model training & reloadability tests
│   └── test_excel_sync.py              # Shared Excel workbook logging & SQLite rebuild tests
│
└── reports/                            # Generated Verification Log Reports
    ├── test-results.txt                # Empirical pytest run results
    ├── frontend-build.txt              # Production Vite compilation logs
    └── sample-output.txt               # System startup & API response logs
```
