# GEMINI.md - Super Over Alchemy Context & Guidelines

## 🚀 Project Overview

**Super Over Alchemy** is an AI-powered video analysis platform leveraging Google Gemini AI for multimodal scene analysis, automated video processing, and content understanding.

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
├── scripts/                   # Shell scripts for build, testing & deployment
│   ├── pre-deploy.sh          # Master pre-deployment lint, type & build check
│   ├── deploy-gcp.sh          # Automated GCP Cloud Build & Cloud Run deployment
│   ├── deploy-sandbox.sh      # Sandbox VM Docker build & Cloud Run deployer
│   ├── launch-sandbox.sh      # Sandbox VM launcher with Shielded Secure Boot
│   ├── remote-test.sh         # Remote sandbox test orchestrator
│   └── run_tests.sh           # Master test runner script
├── docs/                      # Technical documentation & sequence diagrams
├── config.py                  # Environment configuration & settings
├── scene_analysis_schema.json # JSON Schema for Gemini scene analysis output
└── requirements.txt           # Python dependencies
```

---

## 🛠 Command Reference

### **Pre-Deployment Verification**
```bash
# Run all pre-deploy checks (Python lint, mypy types, pytest suite, frontend build)
./scripts/pre-deploy.sh

# Run with auto-formatting
./scripts/pre-deploy.sh --fix
```

### **Testing**
Run tests using the project test runner:
```bash
# Run all tests
./scripts/run_tests.sh all

# Run specific test suites
./scripts/run_tests.sh api
./scripts/run_tests.sh worker
./scripts/run_tests.sh libs
./scripts/run_tests.sh unit
./scripts/run_tests.sh integration

# Run with coverage report
./scripts/run_tests.sh all true
```

### **Code Quality & Linting**
```bash
# Type checking
mypy --config-file mypy.ini api libs workers

# Linting & Formatting
ruff check .
ruff format --check .
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

## Coding instructions
1. DRY: no code duplicates
2. Semantic logging: when, what, why, who, where, and how
3. OWASP: secure coding practices to ensure no vulnerabilities like XSS, CSRF, SQL injection, RCE, etc.
4. SOLID: single responsibility, open/closed, Liskov substitution, interface segregation, dependency inversion
5. Clean Architecture: follow clean architecture principles
6. [Critical] No brute force: Always ensure you optimize data structures and most suitable well-known algorithms


