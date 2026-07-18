"""``pbp`` stage: join scoring events to the official play-by-play (V2).

The score bug tells us *that* a basket was made, its team, and its points — but
not *who* scored or the shot flavor. The official play-by-play (ESPN) does, for
every play, with no per-clip labelling. This stage resolves ``game_id`` to a
normalized PBP artifact; fusion (``timeline._enrich_with_pbp``) does the per-event
join and attaches the authoritative scorer name + jersey + shot type.

The join key is the **score after the play**. Scores only increase and each
scoring play increments exactly one side, so the ``(away, home)`` pair after a
made basket is globally unique — an exact key. The score bug's ``score_after``
maps to a PBP play with the game clock as a secondary confirmation. Orientation
(which of the bug's left/right is away vs home) is resolved by *team name*, never
by position.

Offline-first: the PBP is fetched once into a local JSON (see
``scripts/basketball_fetch_pbp.py``); the runtime path is pure. If no game id /
cache / network is available the stage writes a skipped marker and the pipeline
continues (jersey falls back to the scorer graphic / ASR).
"""

from __future__ import annotations

import json
import logging
import re
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from libs.basketball.scorebug import map_abbr_to_team, normalize_abbr

logger = logging.getLogger(__name__)

DEFAULT_LEAGUE = "mens-college-basketball"
_CORE = "https://sports.core.api.espn.com/v2/sports/basketball/leagues"
_SITE = "https://site.api.espn.com/apis/site/v2/sports/basketball"
_USER_AGENT = "Mozilla/5.0 (compatible; superover-basketball/1.0)"

_ATHLETE_RE = re.compile(r"/athletes/(\d+)")
_TEAM_RE = re.compile(r"/teams/(\d+)")
# The scorer is the leading name in the play text: "K.J. Adams Jr. made Layup."
_SCORER_RE = re.compile(r"^(.*?)\s+(?:made|missed)\b", re.IGNORECASE)


def _norm_name(name: Optional[str]) -> str:
    """Lowercase, strip punctuation/suffixes for roster name matching."""
    if not name:
        return ""
    s = re.sub(r"[.'`-]", "", name.lower())
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", s)
    return re.sub(r"\s+", " ", s).strip()


def _athlete_id_from_ref(ref: str) -> Optional[str]:
    m = _ATHLETE_RE.search(ref or "")
    return m.group(1) if m else None


def _team_id_from_ref(ref: str) -> Optional[str]:
    m = _TEAM_RE.search(ref or "")
    return m.group(1) if m else None


def _scorer_name_from_text(text: str) -> Optional[str]:
    m = _SCORER_RE.match(str(text or "").strip())
    return m.group(1).strip() if m else None


def normalize_shot_type(type_text: Optional[str], play_text: Optional[str], score_value: Optional[int]) -> str:
    """Map an ESPN play type/text to a coarse shot flavor.

    Points win where they are decisive: a +3 is always a 3PT (its ESPN type is
    "JumpShot"), a +1 is a free throw. The 2PT flavor comes from the text.
    """
    t = f"{type_text or ''} {play_text or ''}".lower()
    if "free throw" in t or score_value == 1:
        return "ft"
    if "three point" in t or "3-pt" in t or score_value == 3:
        return "3pt"
    if "dunk" in t:
        return "dunk"
    if "tip" in t:
        return "tip"
    if "layup" in t or "lay up" in t:
        return "layup"
    if "jump" in t:
        return "jumper"
    return "other"


def _team_block(competitor: Dict[str, Any]) -> Dict[str, Any]:
    team = competitor.get("team") or {}
    abbrev = team.get("abbreviation") or ""
    return {
        "id": str(team.get("id")) if team.get("id") is not None else None,
        "abbrev": abbrev,
        "displayName": team.get("displayName"),
        "key": map_abbr_to_team(normalize_abbr(abbrev)),
    }


def _roster(summary_json: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """athlete id -> {jersey, name}, plus normalized-name -> jersey fallbacks."""
    by_id: Dict[str, Dict[str, Any]] = {}
    by_name: Dict[str, str] = {}
    for team in (summary_json.get("boxscore") or {}).get("players", []):
        for stat in team.get("statistics", []):
            for entry in stat.get("athletes", []):
                a = entry.get("athlete") or {}
                aid = str(a.get("id")) if a.get("id") is not None else None
                jersey = a.get("jersey")
                if aid:
                    by_id[aid] = {"jersey": jersey, "name": a.get("displayName")}
                for nm in (a.get("displayName"), a.get("shortName")):
                    if nm and jersey is not None:
                        by_name[_norm_name(nm)] = jersey
    return {"by_id": by_id, "by_name": by_name}


def normalize_game(
    game_id: str, league: str, plays_json: Dict[str, Any], summary_json: Dict[str, Any]
) -> Dict[str, Any]:
    """Build the self-contained normalized PBP artifact (see module docstring)."""
    competitors = ((summary_json.get("header") or {}).get("competitions") or [{}])[0].get("competitors", [])
    away: Dict[str, Any] = {}
    home: Dict[str, Any] = {}
    for c in competitors:
        block = _team_block(c)
        if c.get("homeAway") == "away":
            away = block
        elif c.get("homeAway") == "home":
            home = block

    roster = _roster(summary_json)
    items = plays_json.get("items") or plays_json.get("plays") or []
    plays: List[Dict[str, Any]] = []
    for p in items:
        if not (p.get("scoringPlay") or p.get("shootingPlay")):
            continue  # keep only shot plays (made or missed); Phase 2 uses misses
        shooter = next((x for x in p.get("participants", []) if x.get("type") == "shooter"), None)
        aid = _athlete_id_from_ref((shooter or {}).get("athlete", {}).get("$ref", "")) if shooter else None
        rec = roster["by_id"].get(aid or "", {})
        name = rec.get("name")
        jersey = rec.get("jersey")
        if name is None:
            name = _scorer_name_from_text(p.get("text", ""))
        if jersey is None and name:
            jersey = roster["by_name"].get(_norm_name(name))
        team_id = _team_id_from_ref((p.get("team") or {}).get("$ref", ""))
        scoring_team = "away" if team_id == away.get("id") else ("home" if team_id == home.get("id") else None)
        clk = p.get("clock") or {}
        score_value = p.get("scoreValue")
        plays.append(
            {
                "seq": p.get("sequenceNumber"),
                "period": (p.get("period") or {}).get("number"),
                "clock": clk.get("displayValue"),
                "clock_sec": clk.get("value"),
                "scoring_play": bool(p.get("scoringPlay")),
                "made": bool(p.get("scoringPlay")),
                "score_value": score_value,
                "away_score": p.get("awayScore"),
                "home_score": p.get("homeScore"),
                "scoring_team": scoring_team,
                "text": str(p.get("text", "")),
                "scorer_name": name,
                "scorer_jersey": str(jersey) if jersey is not None else None,
                "shot_type": normalize_shot_type((p.get("type") or {}).get("text"), p.get("text"), score_value),
            }
        )
    return {"game_id": str(game_id), "league": league, "teams": {"away": away, "home": home}, "plays": plays}


def build_score_index(plays: List[Dict[str, Any]]) -> Dict[Tuple[int, int], Dict[str, Any]]:
    """(away_score, home_score) -> the unique made scoring play at that state.

    A collision (two made plays reaching the same score pair) is impossible in a
    real game, but if the feed ever produced one we keep the first.
    """
    index: Dict[Tuple[int, int], Dict[str, Any]] = {}
    for p in plays:
        if not p.get("made"):
            continue
        a, h = p.get("away_score"), p.get("home_score")
        if a is None or h is None:
            continue
        index.setdefault((int(a), int(h)), p)
    return index


@dataclass
class PbpMatch:
    play: Dict[str, Any]
    method: str  # "score_exact" | "score_exact_clock" | "clock_fallback"
    orientation_known: bool
    confidence: float


def match_score_after(
    score_after: List[Optional[int]],
    left_key: Optional[str],
    right_key: Optional[str],
    clock_read_sec: Optional[float],
    away_key: Optional[str],
    home_key: Optional[str],
    score_index: Dict[Tuple[int, int], Dict[str, Any]],
    plays: List[Dict[str, Any]],
    clock_tol_sec: float,
) -> Optional[PbpMatch]:
    """Match a made event's ``score_after`` to a PBP play (see module docstring)."""
    if not score_after or len(score_after) < 2 or score_after[0] is None or score_after[1] is None:
        return None
    left, right = int(score_after[0]), int(score_after[1])

    # 1. Orientation from team names (never positions).
    orientation_known = False
    if left_key and right_key and away_key and home_key:
        if left_key == away_key and right_key == home_key:
            candidates = [(left, right)]
            orientation_known = True
        elif left_key == home_key and right_key == away_key:
            candidates = [(right, left)]
            orientation_known = True
        else:
            candidates = [(left, right), (right, left)]
    else:
        candidates = [(left, right), (right, left)]
    candidates = list(dict.fromkeys(candidates))  # dedupe (symmetric ties)

    # 2. Exact score match.
    hits: List[Dict[str, Any]] = []
    seen = set()
    for pair in candidates:
        play = score_index.get(pair)
        if play is not None and id(play) not in seen:
            hits.append(play)
            seen.add(id(play))
    if len(hits) == 1:
        conf = 0.98 if orientation_known else 0.9
        return PbpMatch(hits[0], "score_exact", orientation_known, conf)
    if len(hits) >= 2:
        if clock_read_sec is None:
            return None  # ambiguous, no clock to break the tie -> no attribution
        best = min(hits, key=lambda p: abs(float(p.get("clock_sec") or 1e9) - clock_read_sec))
        if abs(float(best.get("clock_sec") or 1e9) - clock_read_sec) <= clock_tol_sec:
            return PbpMatch(best, "score_exact_clock", orientation_known, 0.9)
        return None

    # 3. Clock fallback for an OCR score error: nearby score AND nearby clock.
    if clock_read_sec is None:
        return None
    best_play = None
    best_cost: Tuple[int, float] = (99, 1e9)
    for p in plays:
        if not p.get("made"):
            continue
        a, h = p.get("away_score"), p.get("home_score")
        if a is None or h is None:
            continue
        l1 = min(abs(a - left) + abs(h - right), abs(a - right) + abs(h - left))
        if l1 > 2:
            continue
        dclock = abs(float(p.get("clock_sec") or 1e9) - clock_read_sec)
        if dclock > clock_tol_sec:
            continue
        cost = (l1, dclock)
        if cost < best_cost:
            best_cost, best_play = cost, p
    if best_play is not None:
        return PbpMatch(best_play, "clock_fallback", orientation_known, 0.7)
    return None


def recover_silent_miss(
    plays: List[Dict[str, Any]],
    observed_scores: set,
    clock_range: Tuple[float, float],
    period: Optional[int],
    clock_pad_sec: float,
) -> Optional[Dict[str, Any]]:
    """Find the single PBP missed shot consistent with a clip's observed state.

    Phase 2 recall: for a clip the pipeline scored *no* events on (silent — e.g.
    a missed free throw where the rim was never detected), the PBP is the only
    source. A missed shot leaves the score unchanged, so a recoverable miss must
    have a ``(away, home)`` pair the clip actually observed, within its
    game-clock window and period. Returns the play only when **exactly one** such
    miss exists — an ambiguous window (several candidate misses) yields ``None``,
    preferring no event over a wrong one, so this can only recover or decline,
    never fabricate.
    """
    if period is None:
        return None
    lo, hi = clock_range[0] - clock_pad_sec, clock_range[1] + clock_pad_sec
    cands = [
        p
        for p in plays
        if not p.get("made")
        and p.get("period") == period
        and (p.get("away_score"), p.get("home_score")) in observed_scores
        and lo <= float(p.get("clock_sec") if p.get("clock_sec") is not None else -1) <= hi
    ]
    return cands[0] if len(cands) == 1 else None


# --- live fetch (script + optional stage fallback only) --------------------


def _get_json(url: str, timeout: int = 60) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — fixed ESPN hosts
        return json.load(resp)


def fetch_plays(game_id: str, league: str = DEFAULT_LEAGUE) -> Dict[str, Any]:
    return _get_json(f"{_CORE}/{league}/events/{game_id}/competitions/{game_id}/plays?limit=1000")


def fetch_summary(game_id: str, league: str = DEFAULT_LEAGUE) -> Dict[str, Any]:
    return _get_json(f"{_SITE}/{league}/summary?event={game_id}")


def fetch_game(game_id: str, league: str = DEFAULT_LEAGUE) -> Dict[str, Any]:
    """Fetch + normalize a game's PBP (network). Used by the fetch script and the
    optional live-fetch fallback in ``run_stage``."""
    return normalize_game(game_id, league, fetch_plays(game_id, league), fetch_summary(game_id, league))


# --- identify_game (scale path — NOT implemented) --------------------------


def identify_game(teams: List[str], date: Optional[str] = None) -> Optional[str]:  # pragma: no cover
    """Resolve a clip to an ESPN game_id from its teams + date + score progression.

    The scale path for arbitrary footage: query ESPN's scoreboard for ``date``,
    filter by the two team keys, then confirm by aligning the clip's score_after
    sequence to a candidate game's PBP. Not implemented — the eval set supplies
    ``game_id`` directly (manifest top-level / BASKETBALL_PBP_GAME_ID).
    """
    raise NotImplementedError("game auto-identification is a future scale feature")


def _cache_dir(settings: Any) -> Path:
    configured = getattr(settings, "pbp_cache_dir", "") or ""
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / "evals" / "basketball" / "datasets" / "pbp"


def run_stage(ctx: Any) -> None:  # ctx: libs.basketball.stages.StageContext
    """``pbp`` stage: publish the game's normalized PBP into the clip cache."""
    if not ctx.force and ctx.cache.is_warm(ctx.stage):
        return

    def _skip(reason: str) -> None:
        logger.warning("pbp: skipping for clip %s (%s)", ctx.clip_id, reason)
        ctx.cache.write_json(ctx.stage, {"clip_id": ctx.clip_id, "skipped": True, "reason": reason})

    game_id = str(getattr(ctx.settings, "pbp_game_id", "") or "").strip()
    if not game_id:
        _skip("no game_id configured (BASKETBALL_PBP_GAME_ID / manifest game_id)")
        return
    league = str(getattr(ctx.settings, "pbp_league", DEFAULT_LEAGUE) or DEFAULT_LEAGUE)
    cache_file = _cache_dir(ctx.settings) / f"{game_id}.json"

    if cache_file.is_file():
        game = json.loads(cache_file.read_text(encoding="utf-8"))
    elif bool(getattr(ctx.settings, "pbp_allow_fetch", False)):
        try:
            game = fetch_game(game_id, league)
        except Exception as exc:  # noqa: BLE001 — a fetch failure must not break the pipeline
            _skip(f"live fetch failed: {exc}")
            return
    else:
        _skip(f"no cached PBP for {game_id} (run scripts/basketball_fetch_pbp.py --game-id {game_id})")
        return

    logger.info("pbp: %d play(s) for game %s (clip %s)", len(game.get("plays", [])), game_id, ctx.clip_id)
    ctx.cache.write_json(ctx.stage, {"clip_id": ctx.clip_id, **game})  # warm marker last
