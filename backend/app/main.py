from __future__ import annotations

import logging
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.ollama_client import OLLAMA_BASE
from app.ollama_client.warmup import REQUIRED_MODELS, warm_required_models
from app.pipeline import AUTO_DETECT, LOW_CONFIDENCE_WARNING, SUPPORTED_FRAMEWORKS, detect_source, run_pipeline

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


class DetectRequest(BaseModel):
    code: str = Field(..., min_length=1)
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
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "service": "frontend-code-translator-api",
        "pipeline": "detection -> ast/ir -> translation",
        "frontend": str(FRONTEND_DIST) if FRONTEND_DIST else None,
        "ollama_models": OLLAMA_WARMUP_STATUS,
    }


@app.get("/api/frameworks")
def frameworks() -> dict:
    concrete = sorted(SUPPORTED_FRAMEWORKS)
    return {
        "source": [AUTO_DETECT, *concrete],
        "target": concrete,
    }


@app.post("/api/detect")
async def detect_endpoint(payload: DetectRequest) -> dict:
    try:
        detection = await run_in_threadpool(
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
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/ir")
async def ir_endpoint(payload: PipelineRequest) -> dict:
    return await _run_pipeline_endpoint(payload, stop_after="ir")


@app.post("/api/pipeline")
async def pipeline_endpoint(payload: PipelineRequest) -> dict:
    return await _run_pipeline_endpoint(payload, stop_after=payload.stop_after)


@app.post("/api/translate")
async def translate_endpoint(payload: PipelineRequest) -> dict:
    return await _run_pipeline_endpoint(payload, stop_after="translate")


async def _run_pipeline_endpoint(payload: PipelineRequest, stop_after: StopAfter) -> dict:
    try:
        result = await run_in_threadpool(
            run_pipeline,
            payload.code,
            payload.target_framework,
            payload.source_framework,
            payload.use_llm_detection,
            stop_after,
        )
        return result.to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        message = str(exc)
        status_code = 503 if "Ollama" in message or OLLAMA_BASE in message else 500
        raise HTTPException(status_code=status_code, detail=message) from exc


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
