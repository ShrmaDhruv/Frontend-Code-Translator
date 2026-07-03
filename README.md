# Front-End Converter

Front-End Converter is an AI-assisted web application that translates frontend code between **React**, **Vue**, **Angular**, and **vanilla HTML/JavaScript**. It combines rule-based framework detection, an intermediate representation (IR) extraction layer, and local LLM-powered code generation through Ollama.

## Features

- Detects source framework automatically or accepts manual source selection.
- Converts frontend snippets between React, Vue, Angular, and HTML.
- Uses a staged pipeline: detection → AST/IR extraction → translation → cleaning/validation.
- Provides a React-based editor UI for input code, translated output, status, confidence, warnings, and errors.
- Exposes FastAPI endpoints for detection, IR generation, and full translation.
- Supports Docker deployment with an Ollama service for local model inference.

## Tech Stack

### Frontend
- React
- Parcel
- JavaScript / JSX
- CSS

### Backend
- Python
- FastAPI
- Pydantic
- Uvicorn

### AI / Pipeline
- Ollama
- Qwen / Phi-style local chat clients
- Rule-based framework detection
- Framework-neutral IR schema
- Translation response cleaning and validation

### DevOps
- Docker
- Docker Compose

## Project Structure

```text
.
├── App.jsx                    # React entry point
├── index.html                 # Parcel HTML entry
├── backend.py                 # FastAPI backend server
├── pipeline.py                # Main detection → IR → translation orchestrator
├── ast_layer/                 # Framework extractors and IR builder/schema/validator
├── layer3/                    # LLM fallback detection for ambiguous inputs
├── ollama_client/             # Ollama client and model warmup helpers
├── phi_client/                # Translation model client wrapper
├── rules/                     # Regex-based framework detection rules
├── src/                       # React frontend application
├── testing/                   # Tests and detection utilities
├── translation/               # Translation prompt, cleaner, validator, and tests
├── dockerfile                 # Multi-stage frontend/backend Docker build
└── docker-compose.yml         # Backend + Ollama service setup
```

## How the Pipeline Works

1. **Input**: The user pastes frontend code and chooses a target framework.
2. **Detection**: The backend identifies the source framework using weighted rules. If the result is ambiguous, an Ollama-backed LLM detector can be used.
3. **IR Extraction**: Framework-specific extractors collect structural hints such as props, state, lifecycle hooks, imports, methods, template bindings, and styles.
4. **IR Building**: The hints are converted into a framework-neutral intermediate representation.
5. **Translation**: The IR and original source code are sent to the local LLM to generate target-framework code.
6. **Cleaning and Validation**: The generated code is cleaned, checked for framework-specific correctness, and retried if validation fails.
7. **Output**: The translated code, confidence, warnings, and errors are returned to the frontend.

## API Endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/health` | Check API health and Ollama warmup status. |
| `GET` | `/api/frameworks` | List supported source and target frameworks. |
| `POST` | `/api/detect` | Detect source framework only. |
| `POST` | `/api/ir` | Run detection and IR extraction. |
| `POST` | `/api/pipeline` | Run the full pipeline or stop at a selected stage. |
| `POST` | `/api/translate` | Run translation. |

## Getting Started

### Prerequisites

- Node.js 20+
- Python 3.11+
- Ollama running locally or through Docker
- npm

### Install Frontend Dependencies

```bash
npm install
```

### Install Backend Dependencies

```bash
pip install -r requirements.txt
```

### Run the Frontend

```bash
npm run dev
```

### Run the Backend

```bash
uvicorn backend:app --host 0.0.0.0 --port 8000
```

By default, the frontend calls `/api/pipeline`. If running frontend and backend separately, configure your dev proxy or update `src/constants.js` to point to your backend URL.

## Running with Docker

```bash
docker compose up --build
```

This starts:

- an Ollama service
- the FastAPI backend serving the built frontend

The backend is exposed on port `80` by the provided compose file.

## Testing

Run the Python test suite:

```bash
python -m pytest -q
```

## Example Use Case

Paste a React component, choose **Vue** as the target framework, and run the pipeline. The application detects React, extracts component structure into IR, translates the logic and markup into Vue syntax, validates the generated code, and displays the result in the output editor.

## Supported Frameworks

- React
- Vue
- Angular
- HTML / vanilla JavaScript

## Notes

- Translation quality depends on the configured local Ollama model.
- The pipeline includes fallback IR generation if Ollama is unavailable during IR extraction.
- Ambiguous detection results may ask for user confirmation or use Layer 3 LLM detection when enabled.
