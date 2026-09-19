import os
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("workwise.groq")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama3-8b-8192")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# Re-export OLLAMA_MODEL as AI_MODEL for backward compatibility with assistant.py
AI_MODEL = GROQ_MODEL if GROQ_API_KEY else os.environ.get("OLLAMA_MODEL", "gemma3:4b")
OLLAMA_MODEL = AI_MODEL  # backward compat alias


def check_ollama_status() -> Dict[str, Any]:
    """
    Checks if the AI backend is available.
    Checks Groq if GROQ_API_KEY is set, otherwise falls back to Ollama.
    """
    if GROQ_API_KEY:
        return _check_groq_status()
    return _check_ollama_local_status()


def _check_groq_status() -> Dict[str, Any]:
    try:
        import httpx
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(f"{GROQ_BASE_URL}/models", headers=headers)
            if resp.status_code == 200:
                return {
                    "online": True,
                    "model": GROQ_MODEL,
                    "model_available": True,
                    "status": "ready",
                    "base_url": GROQ_BASE_URL,
                    "provider": "groq"
                }
        return {"online": False, "model": GROQ_MODEL, "status": f"HTTP {resp.status_code}", "provider": "groq"}
    except Exception as exc:
        return {"online": False, "model": GROQ_MODEL, "status": str(exc), "provider": "groq"}


def _check_ollama_local_status() -> Dict[str, Any]:
    try:
        import httpx
        ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        ollama_model = os.environ.get("OLLAMA_MODEL", "gemma3:4b")
        with httpx.Client(base_url=ollama_url, timeout=3.0) as client:
            resp = client.get("/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("name", "") for m in data.get("models", [])]
                has_model = any(ollama_model in m for m in models)
                return {
                    "online": True,
                    "model": ollama_model,
                    "model_available": has_model,
                    "status": "ready" if has_model else "model_not_found",
                    "base_url": ollama_url,
                    "provider": "ollama"
                }
    except Exception as exc:
        pass
    return {"online": False, "model": "gemma3:4b", "status": "offline", "provider": "ollama"}


def chat_with_gemma(
    messages: List[Dict[str, str]],
    system_prompt: Optional[str] = None,
    temperature: float = 0.3
) -> str:
    """
    Sends a chat request. Routes to Groq if API key is set, else Ollama.
    """
    if GROQ_API_KEY:
        return _chat_with_groq(messages, system_prompt=system_prompt, temperature=temperature)
    return _chat_with_ollama(messages, system_prompt=system_prompt, temperature=temperature)


def _chat_with_groq(
    messages: List[Dict[str, str]],
    system_prompt: Optional[str] = None,
    temperature: float = 0.3
) -> str:
    try:
        import httpx
        payload_messages = []
        if system_prompt:
            payload_messages.append({"role": "system", "content": system_prompt})
        for msg in messages:
            payload_messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})

        payload = {
            "model": GROQ_MODEL,
            "messages": payload_messages,
            "temperature": temperature,
            "max_tokens": 1024,
        }
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(f"{GROQ_BASE_URL}/chat/completions", json=payload, headers=headers)
            if resp.status_code == 200:
                result = resp.json()
                content = result["choices"][0]["message"]["content"].strip()
                return content if content else "I received an empty response."
            else:
                logger.error(f"Groq API error {resp.status_code}: {resp.text}")
                return f"⚠️ Groq API error (HTTP {resp.status_code}). Please check your API key."
    except Exception as exc:
        logger.error(f"Groq chat error: {exc}")
        return f"⚠️ Error communicating with Groq AI: {str(exc)}"


def _chat_with_ollama(
    messages: List[Dict[str, str]],
    system_prompt: Optional[str] = None,
    temperature: float = 0.3
) -> str:
    try:
        import httpx
        ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        ollama_model = os.environ.get("OLLAMA_MODEL", "gemma3:4b")
        payload_messages = []
        if system_prompt:
            payload_messages.append({"role": "system", "content": system_prompt})
        for msg in messages:
            payload_messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})

        payload = {
            "model": ollama_model,
            "messages": payload_messages,
            "stream": False,
            "options": {"temperature": temperature}
        }
        with httpx.Client(base_url=ollama_url, timeout=60.0) as client:
            resp = client.post("/api/chat", json=payload)
            if resp.status_code == 200:
                content = resp.json().get("message", {}).get("content", "").strip()
                return content if content else "Empty response from Ollama."
            return f"⚠️ Ollama error (HTTP {resp.status_code})."
    except Exception as exc:
        return f"⚠️ Ollama is not running. Set GROQ_API_KEY env var to use cloud AI, or start Ollama locally."
