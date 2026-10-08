# Front-End Converter

Front-End Converter is an AI-assisted web application that translates frontend code between **React**, **Vue**, **Angular**, and **vanilla HTML/JavaScript**. It combines rule-based framework detection, an intermediate representation (IR) extraction layer, and local LLM-powered code generation through Ollama.

## Features

- Detects source framework automatically or accepts manual source selection.
- Converts frontend snippets between React, Vue, Angular, and HTML.
- Uses a staged pipeline: detection → AST/IR extraction → translation → cleaning/validation.
- Provides a React-based editor UI for input code, translated output, status, confidence, warnings, and errors.
- Runs a live preview of the source and the translated component in a sandboxed frame (Sandpack).
- Keeps translations faithful: no CSS the source does not have, and libraries made for the source framework (for example `react-bootstrap`) are replaced instead of copied.
- Measured with an evaluation suite: a 48-case golden dataset and a 33-case prompt-injection attack set (see [Evaluation](#evaluation)).
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
- Qwen2.5-Coder models (3B for detection/IR review, 14B for translation)
- LangGraph (`StateGraph`) for pipeline orchestration
- Rule-based framework detection, with an LLM fallback for ambiguous input
- tree-sitter parsing into a framework-neutral IR schema
- Translation response cleaning and validation, with errors fed back for up to 3 attempts
- LangSmith for evaluation datasets and experiments
- Security guardrails: input guard, prompt hardening, output capability check

### DevOps
- Docker
- Docker Compose

## Project Structure

```text
.
├── backend/
│   ├── requirements.txt        # Python dependencies
│   └── app/
│       ├── main.py             # FastAPI backend server (app = FastAPI())
│       ├── pipeline.py         # Public entry (run_pipeline, detect_source) + CLI
│       ├── graph/              # LangGraph StateGraph: state, nodes, routing, builder
│       ├── detection/
│       │   ├── rule_detector.py    # Layer 1 rule-based framework detection engine
│       │   ├── rules/              # Weighted regex rules per framework
│       │   └── llm_detector/       # Layer 3 LLM fallback for ambiguous inputs
│       ├── ir/
│       │   ├── pre_parser.py       # Source → summary dict (tree-sitter, regex fallback)
│       │   ├── treesitter/         # Tree-sitter extractors (default)
│       │   ├── regex/              # Legacy regex extractors (fallback)
│       │   ├── builder.py          # Summary → IR (facts | hybrid | llm modes)
│       │   ├── schema.py           # Framework-neutral IR dataclasses
│       │   └── validator.py        # IR validation
│       ├── security/           # Guardrails: API limits, input guard, prompt hardening, output guard
│       ├── ollama_client/      # Shared Ollama client (detection + translation models), retry, warmup
│       └── translation/        # Translation prompts, cleaner, output validator, library mapping, CSS fidelity
├── frontend/
│   ├── index.html              # Parcel HTML entry
│   ├── package.json
│   ├── scripts/                # Parcel dev/build runner
│   └── src/                    # React frontend (main.jsx entry, App.jsx, components/)
├── Dockerfile                  # Multi-stage frontend/backend Docker build
└── docker-compose.yml          # Backend + Ollama service setup
```

## How the Pipeline Works

The pipeline is a LangGraph `StateGraph` (`backend/app/graph/`); each step below is a node, and the branches (LLM detection, IR review, translation retries) are conditional edges.

1. **Input**: The user pastes frontend code and chooses a target framework.
2. **Detection**: The backend identifies the source framework using weighted rules. If the result is ambiguous, an Ollama-backed LLM detector can be used.
3. **IR Extraction**: Framework-specific extractors collect structural hints such as props, state, lifecycle hooks, imports, methods, template bindings, and styles.
4. **IR Building**: The hints are converted into a framework-neutral intermediate representation.
5. **Translation**: The IR and original source code are sent to the local LLM to generate target-framework code.
6. **Cleaning and Validation**: The generated code is cleaned (comments, empty stubs, empty style blocks, missing imports), then checked for framework-specific correctness, for fidelity to the source (no invented CSS, no packages made for another framework, the source's CSS library still loaded), and for capabilities the source does not have (output guard). If any check fails, the errors are fed back and the translation is retried, up to 3 attempts.
7. **Output**: The translated code, confidence, warnings, and errors are returned to the frontend.
8. **Preview** (frontend only): the Preview tab wraps the code in a small project (`frontend/src/preview/sandbox.js`) and runs it in the Sandpack in-browser bundler, inside a frame served from a CodeSandbox origin.

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
cd frontend
npm install
```

### Install Backend Dependencies

```bash
cd backend
python -m venv venv
venv\Scripts\activate   # or `source venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
```

### Run the Whole App

Build the frontend once, then start the backend; it serves the UI and the API together on port 8000:

```bash
cd frontend
npm install
npm run build          # → frontend/dist

cd ../backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open http://localhost:8000. `/health` shows which frontend build is served and the Ollama model warm-up status (warm-up runs in the background, so the server is usable immediately).

The backend looks for the built UI in `FRONTEND_DIST`, then `backend/dist` (Docker image), then `frontend/dist`. Without a build it serves the API only.

Environment variables (in the root `.env`):

| Variable | Purpose |
|---|---|
| `OLLAMA_BASE_URL` | Ollama server URL |
| `CORS_ORIGINS` | Comma-separated origins allowed to call the API from another origin (default: the Parcel dev server, `http://localhost:1234`) |
| `OLLAMA_WARMUP` | `0` disables model warm-up at startup |
| `MODEL_NAME` / `HF_MODEL_NAME` | Translation model (default `qwen2.5-coder:14b`) / small model for detection fallback and IR review (default `qwen2.5-coder:3b`) |
| `TRANSLATION_NUM_CTX` | Context window for the translation model in tokens (default `8192`; Ollama's own default of 4096 is too small for the prompt plus the reply) |
| `IR_MODE` | `hybrid` (default: parser facts, LLM only when they look unreliable), `facts` (no LLM), or `llm` |
| `FRONTEND_DIST` | Override the built-frontend directory |
| `ENABLE_API_DOCS` | `1` serves `/docs`, `/redoc`, `/openapi.json` (off by default) |
| `RATE_LIMIT_PER_MINUTE` | POST requests per client IP per minute (default `10`, `0` disables) |
| `MAX_CONCURRENT_PIPELINES` | Pipelines running at once; others queue (default `2`) |
| `QUEUE_TIMEOUT_SECS` | How long a queued request waits before a 503 (default `60`) |
| `MAX_BODY_BYTES` | Request body limit (default `262144`) |
| `MAX_CODE_CHARS` / `MAX_CODE_LINES` | Input size limits (default `20000` / `1000`) |
| `INJECTION_POLICY` | `block` (default) rejects input with high-risk prompt-injection text; `warn` only warns |

### Frontend Dev Server

`npm run dev` in `frontend/` starts Parcel on port 1234 with hot reload. The dev build calls the backend at `http://127.0.0.1:8000` (`API_BASE` in `frontend/src/constants.js`), so run the backend locally on port 8000 alongside it. The production build calls the API on its own origin.

The CLI pipeline entry point (`backend/app/pipeline.py`) should likewise be run as a module from inside `backend/`: `python -m app.pipeline <file> --target Vue`.

## Running with Docker

```bash
docker compose up --build
```

This starts:

- an Ollama service
- the FastAPI backend serving the built frontend

The backend is exposed on port `80` by the provided compose file.

## Security

Guardrails live in `backend/app/security/`:

- **API limits** (`api_limits.py`): body size limit, per-IP rate limit, concurrent pipeline cap, security headers (CSP, `X-Frame-Options`, `nosniff`), API docs off by default, internal errors (e.g. the Ollama host) never returned to clients.
- **Input guard** (`input_guard.py`): before the graph runs, strips invisible/bidi/tag Unicode characters and chat-template tokens (`<|im_start|>`, `[INST]`, ...) and masks secrets (cloud keys, API tokens, JWTs, private keys). The `check_input` node then enforces size limits, rejects input that isn't code, and scores prompt-injection text (high-risk → blocked with `stage: "input"`, low-risk → warning).
- **Prompt hardening** (`prompt_guard.py`): user code and anything derived from it (IR, summaries) goes into tags with a random per-prompt id; every system prompt says tagged content is data, not instructions; the translation prompt repeats the rules after the input and forbids adding network calls, scripts, or URLs; a canary in the system prompt withholds any output that leaks it.
- **Output guard** (`output_guard.py`, graph node `guard_output`): compares what the translation can do with what the source can do. Network requests, dynamic code (`eval`), cookie/storage access, navigation, raw HTML injection, embedded external content, new URL hosts, or new npm packages that the source does not have fail validation, are fed back for a retry, and the code is withheld if they survive the last attempt.
- **Live preview isolation**: previewed code runs in a cross-origin frame (`*.codesandbox.io`, the only origin allowed by the CSP `frame-src`), so it cannot reach this page or the API. The frame is given no permission to open popups or navigate the top window. Code is only sent to that frame when the Preview tab is opened.

Rate limit and concurrency state are per process; behind a reverse proxy run uvicorn with `--proxy-headers --forwarded-allow-ips=<proxy ip>` so limits apply per real client.

## Library and Style Handling

- **CSS**: the output only carries CSS the source has (stylesheet rules or inline styles). If the source has none, the output has none.
- **Framework-neutral packages** (`lodash`, `axios`, ...) are kept as they are.
- **Packages made for the source framework** are never imported in the target. Known families are mapped: Bootstrap (`react-bootstrap`, `bootstrap-vue-next`, `@ng-bootstrap/ng-bootstrap`), Material (`@mui/material`, `vuetify`, `@angular/material`), Ant Design, routers, and Font Awesome.
- **Bootstrap** is translated to plain elements with Bootstrap CSS classes. The stylesheet is loaded with `import 'bootstrap/dist/css/bootstrap.min.css'` for React and Vue and with a CDN `<link>` for HTML. For Angular, add the stylesheet to the `styles` array in `angular.json`; the result includes a warning saying so.
- Only the Bootstrap mapping has been measured end to end; the other families are covered by unit tests.

## Evaluation

The pipeline is measured with an evaluation harness (LangSmith experiments plus custom evaluators). The golden dataset has 48 examples: four components (counter, todo list, session timer, and a signup card built on a UI library), each written in all four frameworks and translated to the other three, so all 12 framework pairs are covered.

Latest results (`qwen2.5-coder:14b`, one run):

| Metric | Result | What it measures |
|---|---|---|
| Framework detection | 100% (48/48) | The source framework was identified correctly |
| IR extraction recall | 100% | Every expected prop, state value, computed value, method and lifecycle hook was extracted |
| Translation validity | 98% (47/48) | The final output passed every static check: target syntax and structure, fidelity to the source, security |
| No invented CSS | 100% (was 54% before the fidelity checks) | The output's stylesheets contain only CSS the source has |
| Libraries handled correctly | 100% on the 12 library cases (was 42%) | No package made for another framework, no leftover component tags, stylesheet still loaded |
| Behaviour preserved (LLM judge) | 97% | A second model (`gemma3:12b`) judged each required behaviour; measured on the original 36 examples before the fidelity checks were added |
| Prompt-injection attacks blocked | 94% (31/33) | With all guardrail layers on; 79% with prompt hardening alone; no false blocks on 5 benign controls |

How to read these numbers:

- **Validity is static.** The translated code is not executed, so a valid translation is well-formed and faithful by inspection, not proven to behave identically.
- **The behaviour judge is lenient.** On a calibration set with deliberately planted bugs it caught 3 of 7, so 97% is an upper bound.
- **The dataset is small** and made of small components; larger real-world components will score lower.
- **Each figure is a single run**; results vary by a case or two between runs.

The evaluation code, the datasets and the test suite (295 offline tests) are kept out of this repository.

## Example Use Case

Paste a React component, choose **Vue** as the target framework, and run the pipeline. The application detects React, extracts component structure into IR, translates the logic and markup into Vue syntax, validates the generated code, and displays the result in the output editor.

## Supported Frameworks

- React
- Vue
- Angular
- HTML / vanilla JavaScript

## Notes

- Translation quality depends on the configured local Ollama model. The figures in [Evaluation](#evaluation) are for `qwen2.5-coder:14b`.
- The validity checks are static; review translated code before using it.
- The pipeline includes fallback IR generation if Ollama is unavailable during IR extraction.
- Ambiguous detection results use Layer 3 LLM detection when enabled. If confidence is still low, the pipeline stops and the UI asks the user to pick the source framework, then runs again with that choice.
