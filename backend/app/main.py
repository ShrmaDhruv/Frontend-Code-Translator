from __future__ import annotations

import logging
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.ollama_client import OLLAMA_BASE
from app.ollama_client.warmup import REQUIRED_MODELS, warm_required_models
from app.pipeline import AUTO_DETECT, LOW_CONFIDENCE_WARNING, SUPPORTED_FRAMEWORKS, detect_source, run_pipeline
from app.security.api_limits import (
    MAX_CONCURRENT_PIPELINES,
    QUEUE_TIMEOUT_SECS,
    RATE_LIMIT_PER_MINUTE,
    BodySizeLimitMiddleware,
    PipelineBusy,
    PipelineGate,
    RateLimiter,
    SecurityHeadersMiddleware,
    retry_after_header,
)
from app.security.input_guard import MAX_CODE_CHARS

load_dotenv()

log = logging.getLogger("uvicorn.error")

BACKEND_DIR = Path(__file__).resolve().parents[1]

# Built frontend: FRONTEND_DIST if set, else backend/dist (Docker image), else frontend/dist (local build).
FRONTEND_DIST_CANDIDATES = [
    Path(os.environ["FRONTEND_DIST"]) if os.getenv("FRONTEND_DIST") else None,
    BACKEND_DIR / "dist",
    BACKEND_DIR.parent / "frontend" / "dist",
]

# Only needed when the UI is served from another origin (e.g. the Parcel dev server).
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:1234,http://127.0.0.1:1234").split(",")
    if origin.strip()
]

Framework = Literal["Auto Detect", "React", "Vue", "Angular", "HTML"]
ConcreteFramework = Literal["React", "Vue", "Angular", "HTML"]
StopAfter = Literal["detect", "ir", "translate"]


# Swagger UI / ReDoc / OpenAPI schema are off unless ENABLE_API_DOCS=1.
ENABLE_API_DOCS = os.getenv("ENABLE_API_DOCS", "0") == "1"

MODEL_UNAVAILABLE_MESSAGE = "The translation model is currently unavailable. Try again later."
BUSY_MESSAGE = "The server is busy with other translations. Try again in a minute."


class DetectRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=MAX_CODE_CHARS)
    source_framework: Framework = AUTO_DETECT
    use_llm_detection: bool = True


class PipelineRequest(DetectRequest):
    target_framework: ConcreteFramework = "Vue"
    stop_after: StopAfter = "translate"


class ErrorResponse(BaseModel):
    ok: bool = False
    stage: str = "error"
    message: str


OLLAMA_WARMUP_STATUS: list[dict] = [
    {"model": model, "ok": False, "message": "warm-up pending"} for model in REQUIRED_MODELS
]


def _warm_up_models() -> None:
    """Load the Ollama models in the background so the server starts immediately."""
    global OLLAMA_WARMUP_STATUS
    log.info("Loading required Ollama models: %s", ", ".join(REQUIRED_MODELS))
    try:
        results = warm_required_models()
    except Exception as exc:
        OLLAMA_WARMUP_STATUS = [
            {"model": model, "ok": False, "message": f"warm-up skipped/failed: {exc}"}
            for model in REQUIRED_MODELS
        ]
        log.warning("Ollama warm-up failed; requests will report errors as needed: %s", exc)
        return

    OLLAMA_WARMUP_STATUS = [
        {"model": result.model, "ok": result.ok, "message": result.message}
        for result in results
    ]
    log.info("Ollama warm-up finished: %s", OLLAMA_WARMUP_STATUS)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if os.getenv("OLLAMA_WARMUP", "1") != "0":
        threading.Thread(target=_warm_up_models, name="ollama-warmup", daemon=True).start()
    yield


app = FastAPI(
    title="Frontend Code Translator API",
    version="1.0.0",
    description="Runs detection, AST/IR extraction, and framework translation.",
    lifespan=lifespan,
    docs_url="/docs" if ENABLE_API_DOCS else None,
    redoc_url="/redoc" if ENABLE_API_DOCS else None,
    openapi_url="/openapi.json" if ENABLE_API_DOCS else None,
)

# Starlette runs the last-added middleware first: security headers → CORS → body size limit → routes.
app.add_middleware(BodySizeLimitMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.add_middleware(SecurityHeadersMiddleware)

rate_limiter  = RateLimiter(RATE_LIMIT_PER_MINUTE, window=60)
pipeline_gate = PipelineGate(MAX_CONCURRENT_PIPELINES, QUEUE_TIMEOUT_SECS)


def rate_limit(request: Request) -> None:
    client = request.client.host if request.client else "unknown"
    wait = rate_limiter.hit(client)
    if wait:
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Try again shortly.",
            headers=retry_after_header(wait),
        )


async def _run_gated(func, *args):
    """Run a blocking pipeline call under the concurrency cap, mapping failures to safe HTTP errors."""
    try:
        return await pipeline_gate.run(func, *args)
    except PipelineBusy as exc:
        raise HTTPException(status_code=503, detail=BUSY_MESSAGE, headers={"Retry-After": "30"}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        # Ollama errors carry internal hostnames; log them, return a generic message.
        log.warning("Pipeline runtime error: %s", exc)
        message = str(exc)
        status_code = 503 if "Ollama" in message or OLLAMA_BASE in message else 500
        detail = MODEL_UNAVAILABLE_MESSAGE if status_code == 503 else "Internal server error"
        raise HTTPException(status_code=status_code, detail=detail) from exc


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "service": "frontend-code-translator-api",
        "pipeline": "detection -> ast/ir -> translation",
        "frontend": FRONTEND_DIST is not None,
        "ollama_models": OLLAMA_WARMUP_STATUS,
    }


@app.get("/api/frameworks")
def frameworks() -> dict:
    concrete = sorted(SUPPORTED_FRAMEWORKS)
    return {
        "source": [AUTO_DETECT, *concrete],
        "target": concrete,
    }


@app.post("/api/detect", dependencies=[Depends(rate_limit)])
async def detect_endpoint(payload: DetectRequest) -> dict:
    detection = await _run_gated(
        detect_source,
        payload.code,
        payload.source_framework,
        payload.use_llm_detection,
    )
    return {
        "ok": not detection.ask_user,
        "stage": "detect",
        "detection": detection.__dict__,
        "warnings": [LOW_CONFIDENCE_WARNING] if detection.ask_user else [],
        "errors": [],
    }


@app.post("/api/ir", dependencies=[Depends(rate_limit)])
async def ir_endpoint(payload: PipelineRequest) -> dict:
    return await _run_pipeline_endpoint(payload, stop_after="ir")


@app.post("/api/pipeline", dependencies=[Depends(rate_limit)])
async def pipeline_endpoint(payload: PipelineRequest) -> dict:
    return await _run_pipeline_endpoint(payload, stop_after=payload.stop_after)


@app.post("/api/translate", dependencies=[Depends(rate_limit)])
async def translate_endpoint(payload: PipelineRequest) -> dict:
    return await _run_pipeline_endpoint(payload, stop_after="translate")


async def _run_pipeline_endpoint(payload: PipelineRequest, stop_after: StopAfter) -> dict:
    result = await _run_gated(
        run_pipeline,
        payload.code,
        payload.target_framework,
        payload.source_framework,
        payload.use_llm_detection,
        stop_after,
    )
    return result.to_dict()


@app.exception_handler(Exception)
async def unexpected_error_handler(_, exc: Exception):
    # Full details go to the server log only; clients get a generic message.
    log.exception("Unhandled error", exc_info=exc)
    message = "Internal server error"
    return JSONResponse(
        status_code=500,
        content={"ok": False, "stage": "error", "message": message, "detail": message},
    )


# Mounted last so the API routes above take precedence over the catch-all "/".
FRONTEND_DIST = next(
    (path for path in FRONTEND_DIST_CANDIDATES if path and (path / "index.html").is_file()),
    None,
)
if FRONTEND_DIST:
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
else:
    log.warning("No built frontend found (run `npm run build` in frontend/); serving the API only.")
