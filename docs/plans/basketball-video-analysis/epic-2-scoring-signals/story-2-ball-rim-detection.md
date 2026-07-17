# Story 2: Ball/Rim/Player Detection (Signal B — model)

**Status (2026-07-17): Implemented-with-deviations** — the generic ONNX wrapper + stage are done and tested, but the basketball YOLO fine-tune is pending GPU access: only the COCO smoke-test fallback (person/sports-ball) exists, so no rim/ball_in_basket/number/referee detections on real footage yet; without a configured model the pipeline degrades gracefully to scorebug-only.

## Summary

Fine-tune a nano YOLO on the Roboflow `basketball-player-detection-3` dataset (10 classes incl. `ball`, `rim`, `ball-in-basket`, `number`, `referee`) and wire CPU ONNX inference into the pipeline. Training is a one-time GPU task; inference is CPU-only.

## Tasks

- [ ] Verify dataset license (Roboflow Universe, expect CC BY 4.0); export in YOLO format. *(Pending — procedure documented in `libs/basketball/models/README.md`.)*
- [ ] Fine-tune YOLO11n (fallback: YOLO26n) — Colab or Roboflow hosted training; record training config + metrics in the repo (`libs/basketball/models/README.md`). *(Pending GPU access.)*
- [ ] Export ONNX (and INT8 variant); store under a models dir with checksums; document AGPL implications of the ultralytics toolchain (training only — runtime uses onnxruntime). *(AGPL note + export procedure documented in models/README.md; export itself pending the fine-tune. `*.onnx` gitignored.)*
- [x] `libs/basketball/detect.py`: onnxruntime session (thread count configurable), letterbox pre/post-processing, per-class confidence thresholds; higher input resolution (960+) for ball/rim classes.
- [x] Cache detections per frame under the stage cache; render in `--debug-video`.

## Acceptance Criteria

- Rim detected in ≥ 95% of frames where a rim is visible on eval clips (rims are the easy class); ball detected in enough frames to form trajectories around shots.
- `ball-in-basket` fires on at least half of the actual makes in the eval set (it's a confirmation signal, not the sole detector).
- CPU inference ≤ 100 ms/frame at the chosen resolution on the dev VM (measured and logged).

## Edge Cases

- Two rims visible in wide shots — keep both; downstream logic picks the attacked rim.
- Ball occluded by hands/bodies near the rim (the critical moment) — detection gaps of 2–3 frames must not break downstream trajectory logic.
- Crowd/replay frames with no court visible.

## Functional Tests

- Unit: pre/post-processing round-trip (letterbox coords back to source pixels).
- Integration: detector on 5 labeled eval frames reproduces expected classes above threshold.
- Benchmark script: logs ms/frame on 100 frames (regression-tracked in PR descriptions, not CI-gated).
