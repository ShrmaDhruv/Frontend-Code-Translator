"""
ollama_client

Ollama REST client shared by detection, IR review, and translation.

Usage:
    from app.ollama_client import detection_client, translation_client

    text = translation_client().chat(messages, max_new_tokens=2048)
"""

from app.ollama_client.client import (
    DETECTION_MODEL,
    OLLAMA_BASE,
    OLLAMA_URL,
    TRANSLATION_MODEL,
    OllamaClient,
    detection_client,
    translation_client,
)

__all__ = [
    "OllamaClient",
    "detection_client",
    "translation_client",
    "DETECTION_MODEL",
    "TRANSLATION_MODEL",
    "OLLAMA_BASE",
    "OLLAMA_URL",
]
