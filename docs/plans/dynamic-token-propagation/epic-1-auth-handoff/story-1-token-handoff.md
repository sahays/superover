# Story 1: Google Login & Token Handoff

## Summary
Implement the frontend Google OAuth2 flow and the backend endpoint to persist the token into the shared Docker volume.

## Tasks
- [ ] Integrate Google Identity Services (GIS) in `frontend/app/layout.tsx`.
- [ ] Implement `POST /api/auth/session` in `api/main.py`.
- [ ] Create `libs/auth.py` to handle saving/loading `active_session.json` in `/app/storage`.
- [ ] Ensure all containers have `/app/storage` mounted as a volume in `docker-compose.yml`.

## Acceptance Criteria
- Clicking "Login" on the frontend results in an `active_session.json` file appearing in the shared volume.
- The file contains a valid `access_token` and `project_id`.

## Functional Tests
- Integration: POST `/api/auth/session` with a mock token creates the session file.
- E2E: User logs in, check shared volume for the expected JSON structure.
