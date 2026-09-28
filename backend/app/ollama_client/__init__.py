"""
ollama_client

Local Ollama REST client helpers.

Usage:
    from app.ollama_client import OLClient
"""

from app.ollama_client.local_ollama import MODEL_NAME, OLLAMA_URL, TIMEOUT_SECS, OLClient

__all__ = [
    "OLClient",
    "MODEL_NAME",
    "OLLAMA_URL",
    "TIMEOUT_SECS",
]
