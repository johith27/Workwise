"""
Intent classifier helper for WorkWise AI Assistant.
Trains a lightweight TF-IDF + Logistic Regression model for text query classification.
"""

import json
import joblib
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

INTENT_DATA = [
    ("show available employees", "list_employees"),
    ("who is available to work", "list_employees"),
    ("list team members", "list_employees"),
    ("show pending tasks", "list_tasks"),
    ("what tasks are open", "list_tasks"),
    ("show at risk tasks", "list_tasks"),
    ("who completed the latest task", "latest_completion"),
    ("latest completed task details", "latest_completion"),
    ("show workload for alice", "check_workload"),
    ("what is bob capacity", "check_workload"),
    ("recommend employee for task 1", "recommend_task"),
    ("find best match for task", "recommend_task"),
    ("show allocation history", "view_history"),
    ("export allocation history to excel", "export_excel"),
    ("add a new employee", "add_employee"),
    ("create a new task", "add_task")
]

def train_intent_classifier():
    texts, labels = zip(*INTENT_DATA)
    pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(ngram_range=(1, 2))),
        ('clf', LogisticRegression())
    ])
    pipeline.fit(texts, labels)
    return pipeline

if __name__ == "__main__":
    model = train_intent_classifier()
    out_dir = Path(__file__).resolve().parent.parent / "models"
    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, out_dir / "intent_classifier.pkl")
    print("Intent classifier trained and saved.")
