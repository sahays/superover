# Story 1: Onboarding Verification Page

## Summary
Create a "System Check" page that verifies API enablement and bucket creation, and only shows if the system is not yet configured.

## Tasks
- [ ] Create `frontend/app/onboarding/page.tsx`.
- [ ] Implement `GET /api/system/status` to check APIs (Service Usage API) and GCS buckets.
- [ ] Implement `POST /api/system/bootstrap` to enable APIs and create missing buckets.
- [ ] Create `system_config` collection in Firestore to store `onboarding_completed: true`.

## Acceptance Criteria
- New users are forced into the onboarding flow.
- "Bootstrap" button successfully enables Vertex AI and creates required buckets.
- Returning users bypass this page.

## Edge Cases
- User has insufficient permissions to enable APIs.
- Service Usage API itself is not enabled (must provide manual instructions).

## Functional Tests
- E2E: Login -> Assert redirect to `/onboarding`.
- E2E: Complete onboarding -> Assert redirect to `/media`.
