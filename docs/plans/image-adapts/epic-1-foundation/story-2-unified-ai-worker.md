# Story 2: Unified AI Worker Refactor

## Summary
Refactor the existing `scene_worker.py` into a unified `ai_worker.py` (or extend `scene_worker.py`) to handle both video scene analysis and generative image adaptation.

## Tasks
- [ ] Refactor `workers/scene_worker.py` to poll both `scene_jobs` and `image_jobs`.
- [ ] Implement `_process_image_job(job)` within the worker.
- [ ] Integrate the new `libs/gemini/image_analyzer.py` for image generation.
- [ ] Ensure `token_usage` and `stop_reason` are captured and stored in the job results for both types.
- [ ] Update worker logs to clearly distinguish between Scene and Image tasks.

## Acceptance Criteria
- A single running worker process can handle both `PENDING` scene jobs and `PENDING` image jobs.
- Image results (binary blobs) are correctly saved to GCS.
- Token usage is correctly aggregated and saved for both job types.

## Edge Cases
- Mixed workload: Worker is busy with a 1-hour video while image jobs are waiting.
- API keys/quotas: Ensure image generation doesn't starve the scene analysis quota.

## Functional Tests
- Integration: Unified worker picks up a `scene_job` and then an `image_job` in the same loop.
- E2E: Full lifecycle for an image adapt from API request to GCS persistence using the unified worker.