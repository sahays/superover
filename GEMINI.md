# GEMINI.md - Super Over Alchemy Context & Guidelines

## 🚀 Project Overview

**Super Over Alchemy** is an AI-powered video analysis platform leveraging Google Gemini (Gemini 2.5 Pro) for multimodal scene analysis, automated video processing, and content understanding.

The system utilizes a dual-worker asynchronous processing architecture for handling media transformation (video transcoding, audio extraction) and AI scene analysis (transcription, character identification, key moment extraction, sentiment analysis).

---

## 🏗 System Architecture & Technology Stack

### **Technology Stack**
- **Backend API**: Python 3.10+, FastAPI (`api/`)
- **Worker Infrastructure**: Unified and dedicated background workers (`workers/`)
- **Frontend**: Next.js 15, TypeScript, TailwindCSS, shadcn/ui (`frontend/`)
- **AI Processing**: Google Gemini 2.5 Pro via Vertex AI (`libs/gemini/`)
- **Media Processing**: FFmpeg / Google Cloud Video Transcoder API (`libs/transcoder/`)
- **Cloud Infrastructure**: GCP Cloud Storage, Firestore, Pub/Sub, BigQuery, Bigtable

### **Key Data Flows**
1. **Media Upload & Processing**:
   `Frontend / API` ➡️ `Cloud Storage` ➡️ `Pub/Sub` ➡️ `Media Transcoder Worker`
2. **Scene Analysis**:
   `Processed Media` ➡️ `Custom Prompts & Context` ➡️ `Pub/Sub` ➡️ `Gemini Analysis Worker` ➡️ `Firestore / BigQuery`

---

## 📁 Repository Structure

```
.
├── api/                       # FastAPI REST API implementation
│   ├── main.py                # API entrypoint
│   ├── middleware/            # Auth, CORS, logging middleware
│   ├── models/                # Pydantic request/response schemas
│   └── routes/                # Endpoint handlers (jobs, prompts, storage)
├── workers/                   # Background job workers
│   ├── unified_worker.py      # Main job polling & execution worker
│   └── health.py              # Worker health check endpoint
├── libs/                      # Shared Python modules & services
│   ├── gemini/                # Gemini AI client integrations & prompt formatters
│   ├── transcoder/            # FFmpeg & cloud video processing helpers
│   ├── storage.py             # Cloud Storage integration
│   ├── db/                    # Firestore / DB access layer
│   ├── bigquery/              # BigQuery analytics exporters
│   └── speech/                # Speech-to-text integration helpers
├── frontend/                  # Next.js 15 web application
├── tests/                     # Pytest test suite
│   ├── api/                   # API unit & integration tests
│   ├── workers/               # Worker processing tests
│   └── libs/                  # Shared library tests
├── docs/                      # Technical documentation & sequence diagrams
├── config.py                  # Environment configuration & settings
├── run_tests.sh               # Master test runner script
├── scene_analysis_schema.json # JSON Schema for Gemini scene analysis output
└── requirements.txt           # Python dependencies
```

---

## 🛠 Command Reference

### **Testing**
Run tests using the project test runner:
```bash
# Run all tests
./run_tests.sh all

# Run specific test suites
./run_tests.sh api
./run_tests.sh worker
./run_tests.sh libs
./run_tests.sh unit
./run_tests.sh integration

# Run with coverage report
./run_tests.sh all true
```

Alternatively, invoke `pytest` directly:
```bash
pytest tests/ -v
pytest tests/api/ -v
```

### **Code Quality & Linting**
```bash
# Type checking
mypy --config-file mypy.ini api libs workers

# Linting
ruff check .
```

### **Frontend Development**
```bash
cd frontend
npm run dev      # Start Next.js development server
npm run build    # Production build
npm run lint     # Lint frontend code
```

---

## 📋 Coding Conventions & Guidelines

1. **Strict Type Annotations**: All Python code must include explicit type hints. Use standard `typing` features and Pydantic models for data schemas.
2. **Schema Enforcement**: Scene analysis prompts and responses must adhere strictly to `scene_analysis_schema.json`.
3. **Async / Non-blocking IO**: Heavy media or network tasks in `api` or `workers` must utilize async patterns or delegating worker threads.
4. **Error Handling**: Mask sensitive details in production responses; ensure structured logging across all services.
5. **Testing Requirements**: Any new API route, worker feature, or library utility must include corresponding pytest coverage in `tests/`.
