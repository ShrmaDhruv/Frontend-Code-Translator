"""
backend.py

FastAPI backend for the frontend code translation pipeline.

Run:
    uvicorn backend:app --reload --host 127.0.0.1 --port 8000

Main endpoint:
    POST /api/pipeline

Pipeline:
    detect -> AST/IR -> translate
"""

from __future__ import annotations

import os
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ollama_client.warmup import REQUIRED_MODELS, warm_required_models
from pipeline import AUTO_DETECT, SUPPORTED_FRAMEWORKS, detect_source, run_pipeline

load_dotenv()


OLLAMA_BASE  = os.getenv("OLLAMA_BASE_URL", "http://ec2-13-203-67-50.ap-south-1.compute.amazonaws.com:11434/")

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


app = FastAPI(
    title="Frontend Code Translator API",
    version="1.0.0",
    description="Runs detection, AST/IR extraction, and framework translation.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OLLAMA_WARMUP_STATUS: list[dict] = []


@app.on_event("startup")
def load_ollama_models_on_startup() -> None:
    global OLLAMA_WARMUP_STATUS

    print(f"Loading required Ollama models: {', '.join(REQUIRED_MODELS)}")
    try:
        results = warm_required_models()
    except RuntimeError as exc:
        OLLAMA_WARMUP_STATUS = [
            {
                "model": model,
                "ok": False,
                "message": f"warm-up skipped/failed: {exc}",
            }
            for model in REQUIRED_MODELS
        ]
        print(f"Ollama warm-up failed; API will start and report runtime errors as needed. {exc}")
        return

    OLLAMA_WARMUP_STATUS = [
        {"model": result.model, "ok": result.ok, "message": result.message}
        for result in results
    ]
    print("Required Ollama models loaded.")


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "service": "frontend-code-translator-api",
        "pipeline": "detection -> ast/ir -> translation",
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
            "warnings": ["detection confidence is low"] if detection.ask_user else [],
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
    return JSONResponse(
        status_code=500,
        content={
            "ok": False,
            "stage": "error",
            "message": f"{type(exc).__name__}: {exc}",
        },
    )