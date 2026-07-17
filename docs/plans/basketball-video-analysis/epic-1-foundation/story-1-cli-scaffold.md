# Story 1: CLI Scaffold, Video Decode & Stage Cache

**Status (2026-07-17): Implemented-with-deviations** — config knobs live in a standalone `libs/basketball/config.py` (`BASKETBALL_` env prefix) instead of the repo root `config.py`, so the CLI runs without any GCP environment; `--debug-video` and `--narrate` shipped as real features (Epic 4 / integration), no longer stubs.

## Summary

Create the `libs/basketball/` package and `scripts/basketball_analyze.py` CLI with PyAV-based decoding, two-tier frame sampling, and a per-clip stage cache so every later stage can be developed and re-run in isolation.

## Tasks

- [x] Create `requirements-basketball.txt` (numpy, av, opencv-python-headless, onnxruntime, rapidocr-onnxruntime, supervision) — keep out of `requirements.txt`.
- [x] `libs/basketball/video.py`: PyAV decode with frame-exact PTS; `sample_frames(clip, fps)` base pass; `decode_window(clip, t0, t1)` native-fps re-decode.
- [x] `libs/basketball/timeline.py`: typed event dataclasses `{t, type, team, points, jersey, confidence, evidence[]}` + JSON serialization (fusion logic comes in Epic 2).
- [x] `scripts/basketball_analyze.py`: argparse CLI per repo convention (`sys.path.insert` + repo imports); flags `-o/--output`, `--stage`, `--workdir`, `--debug-video` (stub), `--narrate` (stub). *(Both flags later implemented for real.)*
- [x] Stage-cache layer: each stage writes JSON/npz under `<workdir>/<clip-id>/<stage>/`; `--stage <name>` re-runs one stage against upstream cache.
- [x] Config knobs in `config.py` following existing pattern (e.g. `basketball_base_fps`, `basketball_workdir`), all with defaults so cloud services are unaffected. *(Deviation: standalone `libs/basketball/config.py` with `BASKETBALL_` env prefix — root `config.py` requires GCP env.)*

## Acceptance Criteria

- `python scripts/basketball_analyze.py clip.mp4 -o out.json` runs end-to-end on a local MP4 and emits a (possibly empty) valid events JSON.
- Second run with a warm cache skips decoding (verified by timing/log output).
- Frame timestamps come from PTS, not frame-index × fps assumption.

## Edge Cases

- Variable-frame-rate clips (PTS gaps) — timestamps must remain correct.
- Clip shorter than the sampling interval; corrupt/truncated MP4 → clear error, non-zero exit.
- Workdir on a full disk / not writable.

## Functional Tests

- Unit: `sample_frames` returns monotonically increasing PTS timestamps on a synthetic PyAV-generated clip.
- Unit: cache round-trip — write stage output, reload, byte-identical.
- Integration: CLI on a 5 s synthetic clip produces schema-valid JSON and exit code 0.
