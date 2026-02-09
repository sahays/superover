# Story 1: Gemini 3 Pro Image Preview Integration

## Summary
Implement the core AI analysis component using `gemini-3-pro-image-preview` to detect Points of Interest (POI) and salient bounding boxes in an uploaded image.

## Tasks
- [ ] Create `libs/gemini/image_analyzer.py` modeled after `scene_analyzer.py`.
- [ ] Implement `analyze_image` method using `settings.gemini_image_model`.
- [ ] Design a prompt for Gemini to return JSON containing object labels and coordinates (xmin, ymin, xmax, ymax).
- [ ] Implement cost calculation for image tokens.

## Acceptance Criteria
- `ImageAnalyzer` successfully calls Gemini and parses JSON output.
- Output contains at least one primary subject with bounding box coordinates.
- Token usage is logged correctly.

## Edge Cases
- Image is too large for Gemini (though 50MB is usually fine).
- Gemini returns malformed JSON or blocked content.
- Image has no clear subject (e.g., plain background).

## Functional Tests
- Integration: `ImageAnalyzer.analyze_image` returns structured POI data for a known test image.
- Integration: `ImageAnalyzer` handles `DeadlineExceeded` with retries.
- E2E: Verify that a "blocked" response from Gemini results in a FAILED job status with a clear error.
