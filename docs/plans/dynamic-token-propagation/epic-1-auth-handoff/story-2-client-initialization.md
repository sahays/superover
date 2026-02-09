# Story 2: Global Client Initialization

## Summary
Update all backend libraries (Database, Storage, Gemini) to use the dynamically propagated token instead of static env vars.

## Tasks
- [ ] Implement `get_gcp_credentials()` in `libs/auth.py` with precedence logic.
- [ ] Update `libs/database.py` to initialize `firestore.Client` with dynamic creds.
- [ ] Update `libs/storage.py` to initialize `storage.Client` with dynamic creds.
- [ ] Update `libs/gemini/` analyzers to configure `genai` with dynamic creds.

## Acceptance Criteria
- Backend services function correctly even if `GOOGLE_APPLICATION_CREDENTIALS` is unset, provided a frontend session exists.

## Functional Tests
- Integration: Initialize a `FirestoreDB` instance and verify it uses the token from the session file.
- Integration: Attempt a GCS upload and verify it uses the project context from the session file.
