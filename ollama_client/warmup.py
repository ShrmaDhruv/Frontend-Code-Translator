from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

from ollama_client.local_ollama import MODEL_NAME as QWEN_MODEL
from phi_client.phi3_client import MODEL_NAME as PHI3_MODEL

load_dotenv()

OLLAMA_BASE_URL     = os.getenv("OLLAMA_BASE_URL", "http://ec2-13-203-67-50.ap-south-1.compute.amazonaws.com:11434/")
OLLAMA_CHAT_URL     = f"{OLLAMA_BASE_URL}/api/chat"
OLLAMA_KEEP_ALIVE   = os.getenv("OLLAMA_KEEP_ALIVE", "30m")
WARMUP_TIMEOUT_SECS = int(os.getenv("OLLAMA_WARMUP_TIMEOUT_SECS", "240"))

REQUIRED_MODELS = (QWEN_MODEL, PHI3_MODEL)


@dataclass(frozen=True)
class WarmupResult:
    model: str
    ok: bool
    message: str


def warm_required_models() -> list[WarmupResult]:
    if not OLLAMA_BASE_URL:
        raise RuntimeError(
            "[warmup] OLLAMA_BASE_URL must be set in .env"
        )

    import requests

    session = requests.Session()
    session.get(OLLAMA_BASE_URL, timeout=5).raise_for_status()

    results: list[WarmupResult] = []
    for model in REQUIRED_MODELS:
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": "Reply with OK."},
            ],
            "stream": False,
            "keep_alive": OLLAMA_KEEP_ALIVE,
            "options": {
                "num_predict": 1,
                "temperature": 0,
            },
        }

        try:
            response = session.post(
                OLLAMA_CHAT_URL,
                json=payload,
                timeout=WARMUP_TIMEOUT_SECS,
            )
            response.raise_for_status()
            results.append(WarmupResult(model=model, ok=True, message="loaded"))
        except Exception as exc:
            results.append(WarmupResult(model=model, ok=False, message=str(exc)))

    failed = [result for result in results if not result.ok]
    if failed:
        details = "; ".join(f"{result.model}: {result.message}" for result in failed)
        raise RuntimeError(f"Ollama model warm-up failed: {details}")

    return results