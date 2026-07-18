"""A tiny hand-authored normalized play-by-play fixture (offline, no network).

Reproduces the eval game's relevant score states so the matcher and fusion
enrichment can be unit-tested without hitting ESPN. Mirrors the precedent of
tests/basketball/scorebug_fixtures.py.
"""

from typing import Any, Dict, List


def _clock_sec(disp: str) -> float:
    m, s = disp.split(":")
    return float(m) * 60 + float(s)


def play(period, clock, score_value, away, home, team, name, jersey, shot_type, made=True) -> Dict[str, Any]:
    return {
        "seq": None,
        "period": period,
        "clock": clock,
        "clock_sec": _clock_sec(clock),
        "scoring_play": made,
        "made": made,
        "score_value": score_value,
        "away_score": away,
        "home_score": home,
        "scoring_team": team,
        "text": f"{name} {'made' if made else 'missed'} {shot_type}.",
        "scorer_name": name,
        "scorer_jersey": jersey,
        "shot_type": shot_type,
    }


# away = Kansas (KU), home = Kansas State (KSU) — matches the real eval game.
PLAYS: List[Dict[str, Any]] = [
    play(1, "18:58", 2, 2, 3, "away", "K.J. Adams Jr.", "24", "layup"),  # and-1 field goal
    play(1, "18:58", 1, 3, 3, "away", "K.J. Adams Jr.", "24", "ft"),  # and-1 free throw (same clock)
    play(1, "16:52", 3, 7, 6, "away", "Kevin McCullar Jr.", "15", "3pt"),
    play(1, "14:00", 2, 9, 8, "home", "Will McNair Jr.", "13", "dunk", made=False),  # a missed shot
    play(1, "0:49", 1, 32, 30, "away", "Dajuan Harris", "3", "ft"),
    play(2, "17:00", 2, 41, 32, "home", "Arthur Kaluma", "24", "layup"),
    play(2, "16:17", 3, 41, 35, "home", "Tylor Perry", "2", "3pt"),
    play(2, "5:00", 2, 50, 48, "home", "Cam Carter", "5", "jumper"),  # 2nd half, clock 5:00
    play(3, "5:00", 2, 70, 68, "home", "Arthur Kaluma", "24", "dunk"),  # OT, same clock 5:00, far score
    play(2, "1:00", 2, 41, 41, "home", "Cam Carter", "5", "jumper"),  # symmetric tie 41-41
]


def normalized_game() -> Dict[str, Any]:
    return {
        "game_id": "TEST",
        "league": "mens-college-basketball",
        "teams": {
            "away": {"id": "2305", "abbrev": "KU", "displayName": "Kansas", "key": "kansas"},
            "home": {"id": "2306", "abbrev": "KSU", "displayName": "Kansas State", "key": "kansas-state"},
        },
        "plays": [dict(p) for p in PLAYS],
    }
