import os
import time

import requests

MAX_RETRIES   = int(os.getenv("OLLAMA_MAX_RETRIES", "2"))
BACKOFF_SECS  = (2, 5)


def post_with_retry(session, url: str, payload: dict, timeout: int) -> requests.Response:
    """
    POST to Ollama, retrying only on network-level failures (dropped
    connection, timeout), e.g. when the client's public IP changes mid-request.
    HTTP error statuses are returned as-is for the caller to raise.
    """
    for attempt in range(MAX_RETRIES + 1):
        try:
            return session.post(url, json=payload, timeout=timeout)
        except (requests.ConnectionError, requests.Timeout) as e:
            if attempt == MAX_RETRIES:
                raise
            wait = BACKOFF_SECS[min(attempt, len(BACKOFF_SECS) - 1)]
            print(f"Ollama request failed ({type(e).__name__}), retrying in {wait}s "
                  f"[{attempt + 1}/{MAX_RETRIES}]")
            time.sleep(wait)
