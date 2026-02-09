# Story 1: API & DB Schema for Image Jobs

## Summary

Establish the database collections and API models needed to track image adaptation jobs, ensuring we can store source
image metadata and requested target aspect ratios.

## Tasks

- [ ] Create `ImageJobStatus` Enum in `libs/database.py`.
- [ ] Define `image_jobs` and `image_results` collections in `FirestoreDB`.
- [ ] Add `image_adaptation` to `PROMPT_TYPES` in `api/models/schemas.py`.
- [ ] Create Pydantic models for `CreateImageJobRequest` and `ImageJobResponse`.
- [ ] Add `usage` (input/output tokens) and `stop_reason` fields to `ImageJobResponse` and Firestore schema.
- [ ] Add `crop_overrides` and `confidence_score` fields to the `image_results` schema.
- [ ] Implement `update_image_result_crop` API endpoint for manual tweaks.
- [ ] Refactor `videos` collection references to support generic `asset_id` where applicable.

## Acceptance Criteria

- Firestore has an `image_jobs` collection.
- API can accept a list of target aspect ratios (e.g., ["16:9", "9:16", "1:1"]).
- Job status can be tracked (PENDING, PROCESSING, COMPLETED, FAILED).

## Edge Cases

- Requesting an invalid aspect ratio format (e.g., "square").
- Job document exceeds Firestore size limits if metadata is too large.

## Functional Tests

- Integration: POST `/api/images/jobs` with valid data returns 201 and creates Firestore doc.
- Integration: POST `/api/images/jobs` with missing `video_id` (or `image_id`) returns 422.
- E2E: Create job, poll GET `/api/images/jobs/{id}`, verify status transitions from PENDING.
