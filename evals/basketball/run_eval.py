#!/usr/bin/env python3
"""Score predicted basketball events against the eval manifest.

Predictions are the CLI's output files ({"clip_id": ..., "events": [...]},
see libs/basketball/timeline.py) — pass a single file or a directory of them.
A prediction's clip_id may carry the cache content-hash suffix
("shot_0013-1a2b3c4d"); it is matched to the manifest clip name by prefix.

Matching: greedy 1:1 within ±tolerance of an event's [t, t_end] span (t_end
absent = a point at t). Ground-truth spans are uncertainty windows, so a
prediction inside one matches exactly and the tolerance only applies past the
window's edges. By default only human-verified ground-truth rows are scored
(--include-unverified scores everything); a predicted made basket inside a
no_scoring_expected window is a false positive, while a predicted miss there is
ignored (the window only asserts that nothing was made). Output is a Markdown
table (per clip + aggregate) suitable for pasting into a PR.

    python evals/basketball/run_eval.py --predictions out/           # dir of *.json
    python evals/basketball/run_eval.py --predictions out.json --include-unverified
    python evals/basketball/run_eval.py                              # no predictions -> recall 0
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from libs.basketball.evaluation import (  # noqa: E402
    Manifest,
    load_manifest,
    render_markdown,
    score_clip,
)
from libs.basketball.timeline import Event, predictions_from_dict  # noqa: E402

DEFAULT_MANIFEST = Path(__file__).resolve().parent / "datasets" / "manifest.yaml"


def _normalize_clip_id(clip_id: str, manifest: Manifest) -> str:
    """Map a predictions clip_id (possibly '<name>-<hash8>') to a manifest clip name."""
    if clip_id in manifest.clips:
        return clip_id
    stem = clip_id.rsplit("-", 1)[0]
    if stem in manifest.clips:
        return stem
    return clip_id


def load_predictions(path: Path, manifest: Manifest) -> Dict[str, List[Event]]:
    """Read one predictions file or every *.json in a directory."""
    files = sorted(path.glob("*.json")) if path.is_dir() else [path]
    predictions: Dict[str, List[Event]] = {}
    for file in files:
        try:
            clip_id, events = predictions_from_dict(json.loads(file.read_text(encoding="utf-8")))
        except (ValueError, json.JSONDecodeError) as exc:
            print(f"Warning: skipping unreadable predictions file {file}: {exc}", file=sys.stderr)
            continue
        name = _normalize_clip_id(clip_id, manifest)
        if name not in manifest.clips:
            print(f"Warning: predictions for unknown clip '{clip_id}' ({file.name}) — ignored", file=sys.stderr)
            continue
        predictions.setdefault(name, []).extend(events)
    return predictions


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--predictions", type=Path, default=None, help="Predictions JSON file or directory of them")
    parser.add_argument(
        "--include-unverified",
        action="store_true",
        help="Score all ground-truth rows, not just human-verified ones",
    )
    parser.add_argument(
        "--tolerance", type=float, default=None, help="Matching tolerance in seconds (default: manifest)"
    )
    args = parser.parse_args(argv)

    if not args.manifest.is_file():
        print(f"Error: manifest not found: {args.manifest}", file=sys.stderr)
        return 1
    manifest = load_manifest(args.manifest)
    tolerance = args.tolerance if args.tolerance is not None else manifest.tolerance_sec

    predictions: Dict[str, List[Event]] = {}
    if args.predictions is not None:
        if not args.predictions.exists():
            print(f"Error: predictions path not found: {args.predictions}", file=sys.stderr)
            return 1
        predictions = load_predictions(args.predictions, manifest)

    scores = [
        score_clip(clip_truth, predictions.get(name, []), tolerance, args.include_unverified)
        for name, clip_truth in sorted(manifest.clips.items())
    ]
    print(render_markdown(scores, args.include_unverified, tolerance))
    return 0


if __name__ == "__main__":
    sys.exit(main())
