import os
import json
import pytest
from pathlib import Path
from training.train_model import train_and_save_model, MODEL_PATH, MANIFEST_PATH

def test_model_training_and_manifest():
    manifest = train_and_save_model()

    assert MODEL_PATH.exists()
    assert MANIFEST_PATH.exists()
    assert manifest["model_version"] == "v1.0.0"
    assert "evaluation_metrics" in manifest
    assert manifest["evaluation_metrics"]["roc_auc"] > 0.85
