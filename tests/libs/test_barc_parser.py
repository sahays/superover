"""Tests for libs/engagement/barc_parser.py."""

import pytest

from libs.engagement.barc_parser import parse_barc_csv


pytestmark = pytest.mark.unit


def _csv(rows: str) -> bytes:
    return rows.encode("utf-8")


def test_seconds_format():
    series = parse_barc_csv(_csv("timestamp,engagement\n0,1.0\n10,2.5\n20,3.0\n"))
    assert series.points == [(0.0, 1.0), (10.0, 2.5), (20.0, 3.0)]
    assert series.time_column == "timestamp"
    assert series.score_column == "engagement"


def test_hh_mm_ss_format():
    series = parse_barc_csv(_csv("time,score\n00:00:00,1\n00:00:30.5,2\n00:01:00,3\n"))
    assert series.points == [(0.0, 1.0), (30.5, 2.0), (60.0, 3.0)]


def test_mm_ss_format():
    series = parse_barc_csv(_csv("t,value\n00:00,1\n01:30,2\n"))
    assert series.points == [(0.0, 1.0), (90.0, 2.0)]


def test_alternate_column_names():
    series = parse_barc_csv(_csv("seconds,rating\n5,7.7\n"))
    assert series.points == [(5.0, 7.7)]
    assert series.time_column == "seconds"
    assert series.score_column == "rating"


def test_unsorted_input_is_sorted():
    series = parse_barc_csv(_csv("timestamp,score\n10,1\n0,2\n5,3\n"))
    assert [t for t, _ in series.points] == [0.0, 5.0, 10.0]


def test_skips_malformed_rows():
    csv = "timestamp,score\n0,1\nbad,row\n10,nan\n20,2\n"
    series = parse_barc_csv(_csv(csv))
    # 'nan' parses as float but is non-finite -> skipped
    assert series.points == [(0.0, 1.0), (20.0, 2.0)]


def test_missing_time_column():
    with pytest.raises(ValueError, match="time column"):
        parse_barc_csv(_csv("foo,score\n0,1\n"))


def test_missing_score_column():
    with pytest.raises(ValueError, match="score column"):
        parse_barc_csv(_csv("timestamp,foo\n0,1\n"))


def test_no_valid_rows():
    with pytest.raises(ValueError, match="zero valid rows"):
        parse_barc_csv(_csv("timestamp,score\nbad,row\n"))


def test_real_barc_report_format():
    """Real BARC reports use Start Time + TVR (%) etc. — auto-anchor and parse."""
    csv = (
        "Date,Start Time,End Time,Duration (Mins),Impressions ('000s),TVR (%),Reach ('000s)\n"
        "2026-04-15,20:00:00,20:01:00,1,350,0.45,320\n"
        "2026-04-15,20:01:00,20:02:00,1,420,0.52,380\n"
        "2026-04-15,20:02:00,20:03:00,1,500,0.61,450\n"
    )
    series = parse_barc_csv(_csv(csv))
    # Time column resolves to "Start Time"; score column prefers TVR (%) over Impressions/Reach
    assert series.time_column == "Start Time"
    assert series.score_column == "TVR (%)"
    # First row is anchored to t=0; subsequent rows are seconds offset
    assert [t for t, _ in series.points] == [0.0, 60.0, 120.0]
    assert [s for _, s in series.points] == [0.45, 0.52, 0.61]
    assert series.anchor_offset_sec == 20 * 3600  # 20:00:00 in seconds


def test_handles_thousands_separator_in_score():
    csv = "timestamp,score\n0,\"1,000\"\n10,\"2,500\"\n"
    series = parse_barc_csv(_csv(csv))
    assert [s for _, s in series.points] == [1000.0, 2500.0]


def test_score_with_percent_suffix():
    csv = "timestamp,TVR (%)\n0,0.5%\n10,0.8%\n"
    series = parse_barc_csv(_csv(csv))
    assert [s for _, s in series.points] == [0.5, 0.8]


def test_falls_back_to_impressions_when_no_tvr():
    csv = (
        "Start Time,Impressions ('000s),Reach ('000s)\n"
        "00:00:00,350,300\n"
        "00:00:30,400,350\n"
    )
    series = parse_barc_csv(_csv(csv))
    # No TVR present — Impressions wins next in priority
    assert series.score_column == "Impressions ('000s)"
    assert [s for _, s in series.points] == [350.0, 400.0]


def test_does_not_anchor_when_starts_near_zero():
    """If the first timestamp is already close to zero, don't shift."""
    csv = "timestamp,score\n0,1\n5,2\n10,3\n"
    series = parse_barc_csv(_csv(csv))
    assert series.anchor_offset_sec == 0
    assert [t for t, _ in series.points] == [0.0, 5.0, 10.0]
