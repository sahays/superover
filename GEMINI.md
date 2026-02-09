# GEMINI.md - Super Over Alchemy

## Project Overview
**Super Over Alchemy** is an AI-powered video analysis platform that leverages Google Gemini (Vertex AI / Google AI Studio) to provide intelligent scene understanding, object identification, transcription, and more. It features a dual-worker architecture to separate media processing (FFmpeg-based) from AI-driven analysis.

### Feature-Based Development
The project follows a feature-based solution approach where the documentation in `docs/` serves as the source of truth:
- `docs/plans/`: High-level implementation strategies and roadmap.
- `docs/specs/`: Detailed technical specifications and requirements.
- `docs/user-journeys/`: User experience flows and behavioral definitions.
- `docs/tech/`: Technical debt, architectural decisions, and research.

### Main Technologies
- **Backend:** Python 3.9+, FastAPI, Pydantic, FFmpeg.
- **Frontend:** Next.js 15 (App Router), TypeScript, TailwindCSS, shadcn/ui.
- **AI/ML:** Google Gemini (Gemini 2.5 Pro / 2.0 Flash).
- **Cloud Infrastructure (GCP):**
  - **Firestore:** NoSQL database for jobs, videos, prompts, and results.
  - **Cloud Storage (GCS):** Object storage for media files and context data.
  - **Vertex AI / AI Studio:** Gemini model hosting.
- **Containerization:** Docker (API and Worker images).

### Core Workflows
1. **Media Processing:**
   - Uploads original video/audio to GCS.
   - Workers compress video (multi-resolution) and extract audio using FFmpeg.
   - Status and metadata are stored in Firestore.
2. **Scene Analysis:**
   - Uses processed media and custom prompts.
   - Supports additional context files (text, markdown, JSON) to enhance analysis.
   - Optional chunking for long-form content.
   - Gemini analyzes the content and returns structured (JSON) or unstructured (SRT) results.
   - Tracks token usage and estimated costs.

---

## Building and Running

### Prerequisites
- Python 3.9+
- Node.js 18+ & npm
- FFmpeg installed locally
- Google Cloud SDK configured

### Backend Setup
1. **Install Dependencies:**
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. **Configuration:**
   - Copy `.env.example` to `.env` and fill in GCP and Gemini API details.
3. **Run API:**
   ```bash
   python api/main.py
   ```
   - API is available at `http://localhost:8080` (or `8000` depending on config).
   - Swagger UI: `/docs`.
4. **Run Workers:**
   - Media Worker: `python workers/media_worker.py`
   - Scene Worker: `python workers/ai_worker.py`

### Frontend Setup
1. **Install Dependencies:**
   ```bash
   cd frontend
   npm install
   ```
2. **Run Development Server:**
   ```bash
   npm run dev
   ```
   - Available at `http://localhost:3000`.

### Testing
- Run tests using pytest:
  ```bash
  pytest
  ```
- Or use the provided script:
  ```bash
  ./run_tests.sh
  ```

---

## Development Conventions

### Documentation Standards
All new feature specifications must follow this structure:
1. **Crisp Problem Description**: Clear and concise explanation of the problem being solved.
2. **Key Challenges**: Identification of technical or business hurdles.
3. **Technical Solution**: Summary of the approach and mapping of solutions to each identified problem.
4. **Success/Acceptance Criteria**: Measurable goals and requirements for completion.
5. **FAQs**: Common questions and edge cases.

### Planning Standards
Plans are organized in `docs/plans/<feature-name>/epic<number>-<name>/story<number>-<name>.md`.
Each story must contain:
- **Summary**: Brief/concise problem description.
- **Tasks**: List of implementation steps.
- **Acceptance Criteria**: Requirements for completion.
- **Edge Cases**: Potential failure points or unusual scenarios.
- **Functional Tests**: Single-bullet integration/E2E tests covering critical path (positive and negative).

### Backend (Python)
- **Framework:** FastAPI with asynchronous routes where appropriate.
- **Data Models:** Pydantic models in `api/models/schemas.py` for request/response validation.
- **Database:** Firestore interactions are centralized in `libs/database.py`.
- **Configuration:** Managed via `pydantic-settings` in `config.py`.
- **Logging:** Standard Python logging is used throughout the backend and workers.

### Frontend (TypeScript/React)
- **Framework:** Next.js 15 App Router.
- **Components:** UI components from shadcn/ui located in `frontend/components/ui`.
- **API Client:** Axios-based client in `frontend/lib/api-client.ts`.
- **Styling:** TailwindCSS with `lucide-react` for icons.

### AI Integration
- Uses the `google-generativeai` Python SDK.
- Prompts are managed in Firestore and can be customized via the UI.
- Supports exponential backoff for API retries in `libs/gemini/scene_analyzer.py`.
- Cost calculation logic is implemented based on token usage.

---

## Project Structure
- `api/`: FastAPI routes and application entry point.
- `frontend/`: Next.js application.
- `libs/`: Shared libraries for database, storage, media processing, and Gemini.
- `workers/`: Background job processors for media and AI tasks.
- `docs/`: Architectural diagrams and detailed sequence documentation.
- `tests/`: Comprehensive test suite.
