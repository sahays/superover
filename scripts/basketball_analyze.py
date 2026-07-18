#!/usr/bin/env python3
"""Basketball broadcast-clip analysis CLI.

Runs the registered pipeline stages (libs/basketball/stages.py) over one clip
and writes the fused event timeline as predictions JSON
({"clip_id": ..., "events": [...]}). Stage outputs are cached per clip under
the workdir so re-runs are instant (--force recomputes, --stage re-runs a
single stage against cache). In a default full run, a detect stage with no
configured model degrades gracefully (skipped marker, scorebug-only events);
--stage detect without a model still raises the instructive error.

    python scripts/basketball_analyze.py clip.mp4 -o out.json
    python scripts/basketball_analyze.py clip.mp4 --stage scorebug
    python scripts/basketball_analyze.py clip.mp4 --force --base-fps 5
    python scripts/basketball_analyze.py clip.mp4 -o out.json --debug-video
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from libs.basketball.cache import ClipCache, compute_clip_id  # noqa: E402
from libs.basketball.config import get_settings  # noqa: E402
from libs.basketball.stages import (  # noqa: E402
    STAGE_ORDER,
    StageContext,
    is_implemented,
    resolve_stage,
)
from libs.basketball.timeline import predictions_to_dict  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stderr)
logger = logging.getLogger("basketball_analyze")


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("clip", type=Path, help="Path to the input clip (MP4)")
    parser.add_argument("-o", "--output", type=Path, default=None, help="Events JSON output path (default: stdout)")
    parser.add_argument("--stage", choices=STAGE_ORDER, default=None, help="Re-run a single stage against the cache")
    parser.add_argument("--force", action="store_true", help="Recompute stages even when their cache is warm")
    parser.add_argument("--workdir", type=Path, default=None, help="Stage-cache root (default: settings.workdir)")
    parser.add_argument("--base-fps", type=float, default=None, help="Base sampling fps (default: settings.base_fps)")
    parser.add_argument(
        "--pbp-game-id", default=None, help="ESPN game id for the play-by-play join (default: settings.pbp_game_id)"
    )
    parser.add_argument(
        "--narrate", action="store_true", help="Gemini narration pass (requires GCP env + ADC; see libs/gemini)"
    )
    parser.add_argument(
        "--debug-video",
        action="store_true",
        help="Render an annotated debug MP4 (detections, tracks, scorebug, events) next to the output JSON",
    )
    return parser.parse_args(argv)


def run_one_stage(
    name: str, clip_path: Path, clip_id: str, settings, workdir: Path, force: bool, pipeline: bool = False
) -> None:
    ctx = StageContext(
        stage=name,
        clip_path=clip_path,
        clip_id=clip_id,
        settings=settings,
        cache=ClipCache(workdir, clip_id),
        force=force,
        pipeline=pipeline,
    )
    started = time.perf_counter()
    resolve_stage(name)(ctx)
    logger.info("stage '%s' finished in %.2fs", name, time.perf_counter() - started)


def _stage_is_warm(cache: ClipCache, name: str, settings) -> bool:
    """Warm-cache check, with one exception: a ``{"narrated": false}`` marker
    (from a run without --narrate) must not block a --narrate run."""
    if not cache.is_warm(name):
        return False
    if name == "narrate" and settings.narrate_enabled:
        return bool(cache.read_json("narrate").get("narrated"))
    return True


def main(argv=None) -> int:
    args = parse_args(argv)

    clip_path = args.clip.resolve()
    if not clip_path.is_file():
        print(f"Error: clip not found: {clip_path}", file=sys.stderr)
        return 1

    settings = get_settings()
    overrides = {}
    if args.base_fps is not None:
        overrides["base_fps"] = args.base_fps
    if args.workdir is not None:
        overrides["workdir"] = str(args.workdir)
    if args.pbp_game_id is not None:
        overrides["pbp_game_id"] = args.pbp_game_id
    if args.narrate:
        overrides["narrate_enabled"] = True
    if overrides:
        settings = settings.model_copy(update=overrides)
    workdir = Path(settings.workdir)

    try:
        clip_id = compute_clip_id(clip_path)
    except OSError as exc:
        print(f"Error: cannot read clip: {exc}", file=sys.stderr)
        return 1
    cache = ClipCache(workdir, clip_id)
    logger.info("clip %s -> cache %s", clip_path.name, cache.root)

    try:
        if args.stage:
            # Single-stage mode always recomputes the named stage (and never
            # degrades gracefully — e.g. detect with no model raises).
            run_one_stage(args.stage, clip_path, clip_id, settings, workdir, force=True)
        else:
            for name in STAGE_ORDER:
                if not is_implemented(name):
                    logger.warning("stage '%s' is not implemented yet — skipping", name)
                    continue
                if _stage_is_warm(cache, name, settings) and not args.force:
                    logger.info("stage '%s' cache is warm — skipping", name)
                    continue
                run_one_stage(name, clip_path, clip_id, settings, workdir, force=args.force, pipeline=True)
    except NotImplementedError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # decode errors, corrupt files, full disk, ...
        print(f"Error while processing {clip_path.name}: {exc}", file=sys.stderr)
        return 1

    # Emit the fused event timeline (predictions format); empty until the
    # 'fuse' stage lands in Epic 2.
    if cache.is_warm("fuse"):
        result = cache.read_json("fuse")
        if not isinstance(result, dict) or "events" not in result:
            print("Error: 'fuse' stage output is not in predictions format", file=sys.stderr)
            return 1
        result.setdefault("clip_id", clip_id)
    else:
        result = predictions_to_dict(clip_id, [])

    text = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
        logger.info("wrote %d event(s) to %s", len(result["events"]), args.output)
    else:
        print(text)

    if args.debug_video:
        from libs.basketball.debug_video import render_debug_video  # lazy: pulls in cv2/av

        base = args.output if args.output else clip_path
        debug_path = base.with_suffix(".debug.mp4")
        try:
            render_debug_video(clip_path, cache, settings, debug_path)
        except Exception as exc:
            print(f"Error rendering debug video for {clip_path.name}: {exc}", file=sys.stderr)
            return 1
        logger.info("wrote debug video to %s", debug_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
