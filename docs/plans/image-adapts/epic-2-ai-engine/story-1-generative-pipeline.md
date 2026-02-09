# Story 1: Gemini Image-to-Image Generation

## Summary
Implement the core generative pipeline using `gemini-3-pro-image-preview` to generate finished adaptations. For jobs with multiple aspect ratios, the worker will execute **parallel synchronous calls** to ensure fast delivery (< 60s) and precise control over each format.

## Tasks
- [ ] Implement `generate_adapt(source_image, target_ratio, target_resolution, refinement_prompt)` in `libs/gemini/image_analyzer.py`.
- [ ] Implement `generate_multiple_adapts(source_image, target_ratios, target_resolution)` to orchestrate parallel API calls.
- [ ] Handle Gemini's binary response (image parts/blobs).
- [ ] Explicitly capture `usage_metadata` (input/output tokens) and `finish_reason` from each response.
- [ ] Implement a system prompt that enforces professional composition and high-quality output.
- [ ] Support "Refinement" capability: sending the previously generated image back with a new instruction.

## Acceptance Criteria
- System returns high-quality image bytes for a 16:9 request.
- System can generate a 9:16 vertical version that extends the background intelligently (outpainting).
- Generated images are saved as high-quality JPEGs or PNGs in GCS.

## Edge Cases
- Gemini returns a "Safety Block" (no image returned).
- Generated image resolution doesn't match requested target exactly.
- Multi-image responses (Gemini returning multiple variations).

## Functional Tests
- Integration: `generate_adapt` returns valid image bytes for a test prompt.
- Integration: Verify that `refinement_prompt` is correctly appended to the generation context.
- E2E: Full flow: Upload -> Select 9:16 -> Gemini Generates -> GCS has a new 9:16 image.
