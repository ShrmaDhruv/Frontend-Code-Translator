"""
phi3_client.py

DeepSeek Coder 6.7B client using Ollama's local REST API.
Used by the translation pipeline to generate target framework code.

DeepSeek Coder is used for code translation tasks.
It receives source-code translation prompts and returns translated code.

Singleton pattern ensures one HTTP session is reused across calls.
Lazy import means the requests package is only required at runtime,
so unit tests work without it installed.

Prereqs:
    ollama pull deepseek-coder:6.7b
    ollama serve          # runs on localhost:11434 by default

Install:
    pip install requests python-dotenv
"""

import os
from dotenv import load_dotenv

load_dotenv()

MODEL_NAME   = os.getenv("MODEL_NAME", "qwen2.5-coder:14b")
OLLAMA_BASE  = os.getenv("OLLAMA_BASE_URL", "http://ec2-13-203-67-50.ap-south-1.compute.amazonaws.com:11434/")
TIMEOUT_SECS = int(os.getenv("TIMEOUT_SECS", "180"))

OLLAMA_URL = f"{OLLAMA_BASE}/api/chat"


class Phi3Client:

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def _load(self):
        if self._loaded and hasattr(self, "_session"):
            return

        import requests

        self._loaded = False

        print(f"Connecting to Ollama ({MODEL_NAME}) at {OLLAMA_BASE}...")

        try:
            session = requests.Session()
            probe   = session.get(OLLAMA_BASE, timeout=5)
            probe.raise_for_status()
            self._session = session
            self._loaded  = True
            print("DeepSeek Coder connection ready.")

        except Exception as e:
            raise RuntimeError(f"[Phi3Client] Ollama unreachable at {OLLAMA_BASE}: {e}")

    def chat(
        self,
        messages:       list[dict],
        max_new_tokens: int   = 2048,
        temperature:    float = 0.1,
    ) -> str:
        self._load()

        payload = {
            "model":    MODEL_NAME,
            "messages": messages,
            "stream":   False,
            "options": {
                "num_predict": max_new_tokens,
                "temperature": temperature,
            },
        }

        try:
            response = self._session.post(
                OLLAMA_URL,
                json    = payload,
                timeout = TIMEOUT_SECS,
            )
            response.raise_for_status()

        except Exception as e:
            raise RuntimeError(f"[DeepseekClient] Ollama request failed: {e}")

        return response.json()["message"]["content"].strip()

    def is_available(self) -> bool:
        try:
            import requests
            requests.get(OLLAMA_BASE, timeout=3).raise_for_status()
            return True
        except Exception:
            return False