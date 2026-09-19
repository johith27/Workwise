import os
import logging
from typing import List, Dict, Any, Optional
import httpx

logger = logging.getLogger("workwise.ollama")

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma3:4b")
DEFAULT_TIMEOUT = float(os.environ.get("OLLAMA_TIMEOUT", "60.0"))

def check_ollama_status() -> Dict[str, Any]:
    """
    Checks if Ollama daemon is running and if the requested model is available.
    """
    try:
        with httpx.Client(base_url=OLLAMA_BASE_URL, timeout=3.0) as client:
            resp = client.get("/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("name", "") for m in data.get("models", [])]
                has_model = any(OLLAMA_MODEL in m for m in models)
                return {
                    "online": True,
                    "model": OLLAMA_MODEL,
                    "model_available": has_model,
                    "available_models": models,
                    "base_url": OLLAMA_BASE_URL,
                    "status": "ready" if has_model else "model_not_found"
                }
            return {
                "online": False,
                "model": OLLAMA_MODEL,
                "model_available": False,
                "status": f"HTTP {resp.status_code}",
                "base_url": OLLAMA_BASE_URL
            }
    except Exception as exc:
        return {
            "online": False,
            "model": OLLAMA_MODEL,
            "model_available": False,
            "status": str(exc),
            "base_url": OLLAMA_BASE_URL
        }

def chat_with_gemma(
    messages: List[Dict[str, str]],
    system_prompt: Optional[str] = None,
    temperature: float = 0.3
) -> str:
    """
    Sends a conversational request to Ollama with the Gemma 3:4b model.
    """
    payload_messages = []
    if system_prompt:
        payload_messages.append({"role": "system", "content": system_prompt})
    
    for msg in messages:
        payload_messages.append({
            "role": msg.get("role", "user"),
            "content": msg.get("content", "")
        })

    payload = {
        "model": OLLAMA_MODEL,
        "messages": payload_messages,
        "stream": False,
        "options": {
            "temperature": temperature
        }
    }

    try:
        with httpx.Client(base_url=OLLAMA_BASE_URL, timeout=DEFAULT_TIMEOUT) as client:
            resp = client.post("/api/chat", json=payload)
            if resp.status_code == 200:
                result = resp.json()
                content = result.get("message", {}).get("content", "").strip()
                if content:
                    return content
                return "I received an empty response from Gemma 3:4b."
            else:
                logger.error(f"Ollama API returned status {resp.status_code}: {resp.text}")
                return f"Error communicating with Gemma 3:4b (HTTP {resp.status_code})."
    except httpx.ConnectError:
        logger.warning(f"Could not connect to Ollama at {OLLAMA_BASE_URL}")
        return "⚠️ **Ollama is not running locally.** Please ensure Ollama is started on `http://localhost:11434` with `gemma3:4b` installed (`ollama run gemma3:4b`)."
    except httpx.TimeoutException:
        logger.warning("Timeout while waiting for Gemma 3:4b response.")
        return "⚠️ Request to Gemma 3:4b timed out. The model may be initializing or processing a heavy workload."
    except Exception as exc:
        logger.error(f"Unexpected error in chat_with_gemma: {exc}")
        return f"⚠️ Error communicating with Gemma 3:4b: {str(exc)}"
