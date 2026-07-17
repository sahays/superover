# Story 2: Fact-Constrained Gemini Narration

## Summary

Add the `--narrate` pass: feed the verified event timeline plus the clip to Gemini via the existing `SceneAnalyzer`, producing prose in the established output format (Timestamp / Event Title / Analysis / Category) that never contradicts or invents facts — the LLM owns meaning, signals own timestamps.

## Tasks

- [ ] `libs/basketball/narrate.py`: build prompt embedding the timeline as a fact block (timestamps, outcome, team, points, jersey, confidence); reuse `libs/gemini/scene_analyzer.py:analyze_chunk` with local bytes + `response_schema`.
- [ ] `response_schema` matching the established format: list of `{timestamp_range, event_title, analysis, category}` — one entry per timeline event, key fields echoed for validation.
- [ ] Prompt rules: facts are ground truth; describe play context around them; omit attributes with `null`/low confidence rather than guessing; never add events absent from the timeline.
- [ ] Post-validation: reject/repair narration whose echoed facts (timestamps ±2 s, team, points, jersey) diverge from the timeline; single retry, then fall back to templated text per event.
- [ ] Surface cost/token usage (already returned by `SceneAnalyzer`) in CLI output; `--narrate` remains optional so the perception pipeline stays offline-capable.

## Acceptance Criteria

- Narrated output on eval clips contains exactly the timeline's events — no extra, no missing, no contradicting attribute.
- Post-validation catches an injected fact mismatch in tests (mutation test on a canned Gemini response).
- Output renders in the same shape as the previously reviewed analyses, enabling side-by-side comparison.

## Edge Cases

- Gemini returns fewer/more entries than events → validation fails → retry → template fallback.
- Low-confidence jersey (`null`) — narration must describe the play without a number, not invent one.
- MAX_TOKENS truncation — handled by `SceneAnalyzer`'s continuation loop; verify with a long multi-event clip.

## Functional Tests

- Unit: prompt builder embeds every event field; fact-block golden test.
- Unit: post-validator on canned responses (compliant, wrong jersey, extra event, missing event).
- Integration (`integration` marker, requires ADC): one eval clip end-to-end with `--narrate`; echoed facts match timeline.
