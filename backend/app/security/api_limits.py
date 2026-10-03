"""
API-edge limits (Layer 1): request body size, per-client rate limit,
concurrent pipeline cap, and security response headers.

State is in-process: fine for one uvicorn worker. With several workers or
replicas the rate limit and the pipeline cap must move to a shared store
(e.g. Redis). Behind a reverse proxy run uvicorn with --proxy-headers and
--forwarded-allow-ips so request.client.host is the real client IP.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import threading
import time
from collections import deque

MAX_BODY_BYTES           = int(os.getenv("MAX_BODY_BYTES", str(256 * 1024)))
RATE_LIMIT_PER_MINUTE    = int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))   # 0 disables
MAX_CONCURRENT_PIPELINES = int(os.getenv("MAX_CONCURRENT_PIPELINES", "2"))
QUEUE_TIMEOUT_SECS       = float(os.getenv("QUEUE_TIMEOUT_SECS", "60"))


# ── Rate limiting ─────────────────────────────────────────────────────────────

class RateLimiter:
    """Sliding-window limiter: at most `limit` hits per `window` seconds per key."""

    MAX_KEYS = 10_000

    def __init__(self, limit: int, window: float = 60.0):
        self.limit  = limit
        self.window = window
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str, now: float | None = None) -> float:
        """Record a hit. Returns 0 if allowed, else seconds until the next slot frees up."""
        if self.limit <= 0:
            return 0.0
        now = time.monotonic() if now is None else now
        with self._lock:
            if len(self._hits) > self.MAX_KEYS:
                self._prune(now)
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return self.window - (now - hits[0])
            hits.append(now)
            return 0.0

    def _prune(self, now: float) -> None:
        stale = [key for key, hits in self._hits.items() if not hits or now - hits[-1] >= self.window]
        for key in stale:
            del self._hits[key]


# ── Concurrency cap ───────────────────────────────────────────────────────────

class PipelineBusy(Exception):
    pass


class PipelineGate:
    """At most `limit` pipelines run at once; others wait up to `timeout` seconds."""

    def __init__(self, limit: int, timeout: float):
        self.timeout    = timeout
        self._semaphore = asyncio.Semaphore(max(1, limit))

    async def run(self, func, *args):
        from fastapi.concurrency import run_in_threadpool

        try:
            await asyncio.wait_for(self._semaphore.acquire(), timeout=self.timeout)
        except asyncio.TimeoutError as exc:
            raise PipelineBusy from exc
        try:
            return await run_in_threadpool(func, *args)
        finally:
            self._semaphore.release()


# ── ASGI middleware ───────────────────────────────────────────────────────────

async def _send_json(send, status: int, body: dict) -> None:
    payload = json.dumps(body).encode()
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(payload)).encode())],
    })
    await send({"type": "http.response.body", "body": payload})


class BodySizeLimitMiddleware:
    """Rejects request bodies over max_bytes with 413, with or without a Content-Length header."""

    def __init__(self, app, max_bytes: int = MAX_BODY_BYTES):
        self.app       = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] in ("GET", "HEAD", "OPTIONS"):
            return await self.app(scope, receive, send)

        too_large = {"ok": False, "stage": "error", "message": "Request body too large",
                     "detail": f"Request body too large (limit {self.max_bytes} bytes)"}

        length = dict(scope["headers"]).get(b"content-length")
        if length is not None and length.isdigit() and int(length) > self.max_bytes:
            return await _send_json(send, 413, too_large)

        # Buffer the body (bounded by max_bytes), then replay it to the app.
        chunks, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.max_bytes:
                return await _send_json(send, 413, too_large)
            chunks.append(chunk)
            if not message.get("more_body", False):
                break

        body, replayed = b"".join(chunks), False

        async def replay():
            nonlocal replayed
            if replayed:
                return await receive()
            replayed = True
            return {"type": "http.request", "body": body, "more_body": False}

        await self.app(scope, replay, send)


CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; font-src 'self' data:; connect-src 'self'; "
    # The live preview runs translated code in frames served by the Sandpack bundler.
    "frame-src https://*.codesandbox.io; "
    "object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
)

_SECURITY_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
    (b"cross-origin-opener-policy", b"same-origin"),
]

# Swagger/ReDoc load assets from a CDN, so they get no CSP (only served when ENABLE_API_DOCS=1).
_CSP_EXEMPT = ("/docs", "/redoc", "/openapi.json")


class SecurityHeadersMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        add_csp = not scope["path"].startswith(_CSP_EXEMPT)

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {name.lower() for name, _ in headers}
                headers += [h for h in _SECURITY_HEADERS if h[0] not in present]
                if add_csp and b"content-security-policy" not in present:
                    headers.append((b"content-security-policy", CONTENT_SECURITY_POLICY.encode()))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)


def retry_after_header(seconds: float) -> dict[str, str]:
    return {"Retry-After": str(max(1, math.ceil(seconds)))}
