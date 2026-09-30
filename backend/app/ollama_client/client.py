import os
from functools import lru_cache

from dotenv import load_dotenv

from app.ollama_client.retry import post_with_retry

load_dotenv()

OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://ec2-13-203-67-50.ap-south-1.compute.amazonaws.com:11434/")
OLLAMA_URL  = f"{OLLAMA_BASE}/api/chat"

# Small model: ambiguous-source detection and hybrid IR review.
DETECTION_MODEL        = os.getenv("HF_MODEL_NAME", "qwen2.5-coder:3b")
DETECTION_TIMEOUT_SECS = int(os.getenv("HF_TIMEOUT_SECS", "120"))

# Large model: code translation.
TRANSLATION_MODEL        = os.getenv("MODEL_NAME", "qwen2.5-coder:14b")
TRANSLATION_TIMEOUT_SECS = int(os.getenv("TIMEOUT_SECS", "180"))


class OllamaClient:

    def __init__(self, model: str, timeout_secs: int):
        self.model        = model
        self.timeout_secs = timeout_secs
        self._loaded      = False

    def _load(self):
        if self._loaded and hasattr(self, "_session"):
            return

        import requests

        self._loaded = False

        print(f"Connecting to Ollama ({self.model}) at {OLLAMA_BASE}...")

        try:
            session = requests.Session()
            probe   = session.get(OLLAMA_BASE, timeout=5)
            probe.raise_for_status()
            self._session = session
            self._loaded  = True
            print(f"{self.model} connection ready.")

        except Exception as e:
            raise RuntimeError(f"Ollama unreachable at {OLLAMA_BASE}: {e}")

    def chat(
        self,
        messages:       list[dict],
        max_new_tokens: int   = 512,
        temperature:    float = 0.1,
    ) -> str:
        self._load()

        payload = {
            "model":    self.model,
            "messages": messages,
            "stream":   False,
            "options": {
                "num_predict": max_new_tokens,
                "temperature": temperature,
            },
        }

        try:
            response = post_with_retry(self._session, OLLAMA_URL, payload, self.timeout_secs)
            response.raise_for_status()

        except Exception as e:
            raise RuntimeError(f"Ollama request failed: {e}")

        return response.json()["message"]["content"].strip()

    def is_available(self) -> bool:
        try:
            import requests
            requests.get(OLLAMA_BASE, timeout=3).raise_for_status()
            return True
        except Exception:
            return False


@lru_cache(maxsize=None)
def detection_client() -> OllamaClient:
    """Shared client for the small model (one per process)."""
    return OllamaClient(DETECTION_MODEL, DETECTION_TIMEOUT_SECS)


@lru_cache(maxsize=None)
def translation_client() -> OllamaClient:
    """Shared client for the translation model (one per process)."""
    return OllamaClient(TRANSLATION_MODEL, TRANSLATION_TIMEOUT_SECS)
