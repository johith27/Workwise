import os
import sys
import json
import logging
import datetime
from pathlib import Path
import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("workwise.training")

BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "models"
MODEL_PATH = MODELS_DIR / "workforce_random_forest.pkl"
MANIFEST_PATH = MODELS_DIR / "model_manifest.json"

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

def generate_synthetic_training_data(n_samples: int = 1200, seed: int = 42) -> pd.DataFrame:
    """
    Generates synthetic historical allocation training dataset.
    """
    np.random.seed(seed)
    
    skill_match_ratio = np.random.uniform(0.0, 1.0, n_samples)
    skill_level_surplus = np.random.uniform(-2.0, 3.0, n_samples)
    workload_ratio = np.random.uniform(0.0, 1.2, n_samples)
    capacity_headroom = np.random.uniform(-10.0, 35.0, n_samples)
    location_match = np.random.choice([0.0, 1.0], size=n_samples, p=[0.2, 0.8])
    historical_success_rate = np.random.uniform(0.5, 1.0, n_samples)
    estimated_hours = np.random.uniform(2.0, 40.0, n_samples)
    priority_num = np.random.choice([1.0, 2.0, 3.0, 4.0], size=n_samples, p=[0.2, 0.4, 0.3, 0.1])

    # Target calculation logic:
    # A candidate is suitable (1) if they match skills, have sufficient capacity, and location matches.
    logits = (
        (skill_match_ratio * 4.0) +
        (skill_level_surplus * 0.8) +
        ((1.0 - workload_ratio) * 3.0) +
        (np.clip(capacity_headroom / 10.0, -1.0, 2.0) * 2.0) +
        (location_match * 1.5) +
        (historical_success_rate * 2.0) - 4.5
    )

    prob = 1.0 / (1.0 + np.exp(-logits))
    suitability_class = (prob >= 0.5).astype(int)

    df = pd.DataFrame({
        "skill_match_ratio": skill_match_ratio,
        "skill_level_surplus": skill_level_surplus,
        "workload_ratio": workload_ratio,
        "capacity_headroom": capacity_headroom,
        "location_match": location_match,
        "historical_success_rate": historical_success_rate,
        "estimated_hours": estimated_hours,
        "priority_num": priority_num,
        "suitability_class": suitability_class
    })
    return df

def train_and_save_model() -> dict:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Generating training data...")
    df = generate_synthetic_training_data(n_samples=1500)

    X = df[FEATURE_NAMES]
    y = df["suitability_class"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    logger.info("Training Random Forest Classifier...")
    model = RandomForestClassifier(
        n_estimators=120,
        max_depth=8,
        min_samples_split=4,
        random_state=42
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    acc = float(accuracy_score(y_test, y_pred))
    prec = float(precision_score(y_test, y_pred))
    rec = float(recall_score(y_test, y_pred))
    f1 = float(f1_score(y_test, y_pred))
    roc_auc = float(roc_auc_score(y_test, y_proba))

    logger.info(f"Model Evaluation Metrics -> Accuracy: {acc:.4f}, Precision: {prec:.4f}, Recall: {rec:.4f}, F1: {f1:.4f}, ROC-AUC: {roc_auc:.4f}")

    # Save model artifact
    joblib.dump(model, MODEL_PATH)
    logger.info(f"Model saved to {MODEL_PATH}")

    # Save manifest
    manifest = {
        "model_name": "WorkWise Random Forest Candidate Scorer",
        "model_version": "v1.0.0",
        "trained_at": datetime.datetime.now().isoformat(),
        "algorithm": "RandomForestClassifier",
        "hyperparameters": {
            "n_estimators": 120,
            "max_depth": 8,
            "min_samples_split": 4,
            "random_state": 42
        },
        "features": FEATURE_NAMES,
        "target": "suitability_class",
        "evaluation_metrics": {
            "accuracy": round(acc, 4),
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1_score": round(f1, 4),
            "roc_auc": round(roc_auc, 4)
        },
        "output_interpretation": "Probability of successful allocation (0.0 to 1.0)",
        "train_samples": len(X_train),
        "test_samples": len(X_test)
    }

    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info(f"Model manifest saved to {MANIFEST_PATH}")
    return manifest

if __name__ == "__main__":
    train_and_save_model()
