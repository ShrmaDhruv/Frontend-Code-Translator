"""
phi_client

Local Phi-3 Ollama REST client helpers.

Usage:
    from app.phi_client import Phi3Client
"""

from app.phi_client.phi3_client import MODEL_NAME, OLLAMA_URL, TIMEOUT_SECS, Phi3Client

__all__ = [
    "Phi3Client",
    "MODEL_NAME",
    "OLLAMA_URL",
    "TIMEOUT_SECS",
]
