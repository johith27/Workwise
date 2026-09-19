import os
import json
import logging
from pathlib import Path
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("workwise.llm_assistant")

BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_PATH = BASE_DIR / "training" / "assistant_dataset.json"
MODEL_PATH = BASE_DIR / "models" / "assistant_llm_model.pkl"
MANIFEST_PATH = BASE_DIR / "models" / "assistant_manifest.json"

def train_assistant_model():
    if not DATASET_PATH.exists():
        logger.error(f"Dataset file not found at {DATASET_PATH}")
        return None

    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    texts = [item["text"] for item in dataset]
    intents = [item["intent"] for item in dataset]

    logger.info(f"Training Custom Assistant Model on {len(dataset)} dataset samples...")
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2))),
        ("clf", MultinomialNB())
    ])
    pipeline.fit(texts, intents)

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, MODEL_PATH)

    manifest = {
        "model_name": "WorkWise Assistant Custom NLP & Entity Model",
        "dataset_samples": len(dataset),
        "dataset_path": str(DATASET_PATH),
        "intents": list(set(intents)),
        "status": "Trained & Active"
    }
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info(f"Assistant model saved to {MODEL_PATH}")
    return manifest

if __name__ == "__main__":
    train_assistant_model()
