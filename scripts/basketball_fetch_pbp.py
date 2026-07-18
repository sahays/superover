#!/usr/bin/env python3
"""Fetch + cache an ESPN play-by-play game as a normalized JSON (one-time).

The basketball pipeline is offline-first: the ``pbp`` stage reads a cached
normalized PBP file rather than hitting ESPN on every run. This helper does the
one network fetch and writes the cache, mirroring how ``build_dataset.py``
downloads the clips once.

    python scripts/basketball_fetch_pbp.py --game-id 401603459
    # -> evals/basketball/datasets/pbp/401603459.json
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from libs.basketball import pbp  # noqa: E402

DEFAULT_OUT_DIR = Path(__file__).resolve().parent.parent / "evals" / "basketball" / "datasets" / "pbp"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--game-id", required=True, help="ESPN event/game id (e.g. 401603459)")
    parser.add_argument("--league", default=pbp.DEFAULT_LEAGUE, help="ESPN league slug")
    parser.add_argument("--out", type=Path, default=None, help="Output JSON path (default: datasets/pbp/<id>.json)")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing cache file")
    args = parser.parse_args(argv)

    out = args.out or (DEFAULT_OUT_DIR / f"{args.game_id}.json")
    if out.is_file() and not args.force:
        print(f"{out} already exists (use --force to overwrite)")
        return 0

    try:
        game = pbp.fetch_game(args.game_id, args.league)
    except Exception as exc:  # noqa: BLE001 — a fetch failure is a user-facing error, report it
        print(f"Error: failed to fetch PBP for {args.game_id}: {exc}", file=sys.stderr)
        return 1

    plays = game.get("plays", [])
    made = [p for p in plays if p.get("made")]
    with_jersey = sum(1 for p in made if p.get("scorer_jersey"))
    teams = game.get("teams", {})
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(game, indent=2), encoding="utf-8")
    tmp.replace(out)

    away = (teams.get("away") or {}).get("key") or (teams.get("away") or {}).get("abbrev")
    home = (teams.get("home") or {}).get("key") or (teams.get("home") or {}).get("abbrev")
    print(f"wrote {out}")
    print(f"  {away} (away) vs {home} (home) — {len(plays)} shot plays, {len(made)} made, {with_jersey} with jersey")
    return 0


if __name__ == "__main__":
    sys.exit(main())
