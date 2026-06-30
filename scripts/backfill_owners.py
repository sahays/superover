#!/usr/bin/env python3
"""One-time backfill: tag existing content + invite codes with an `owner` (studio)
for per-tenant conversational-search isolation (Sony / Zee / …).

Auth: uses the attached service account via the GCE/Cloud-Run metadata server
(``google.auth.compute_engine``), bypassing any expired local ``gcloud auth``
ADC — the same approach as ``scripts/fetch-logs.sh``.

Idempotent and safe to re-run. **Dry-run by default**; pass ``--apply`` to write.

Steps:
  1. ``ALTER scene_embeddings_v2 ADD COLUMN IF NOT EXISTS owner STRING``.
  2. ``UPDATE`` owner from ``video_filename`` using the ``content_owners`` markers
     in config (only rows where ``owner IS NULL`` — never clobbers a manual tag).
  3. Stamp Firestore video docs with the same derived owner (keeps re-sync consistent).
  4. Set ``owner`` on invite codes: ``--code-owner CODE=OWNER`` (repeatable, matches
     code value / id / label), else auto-match a code whose label equals a known slug.

Usage:
  python scripts/backfill_owners.py                       # dry-run, prints plan
  python scripts/backfill_owners.py --apply               # write BQ + Firestore videos
  python scripts/backfill_owners.py --apply \\
      --code-owner SONY_CODE_123=sony --code-owner ZEE_CODE_456=zee
"""

import argparse
import logging
import sys

import google.auth.compute_engine
import google.cloud.firestore as firestore  # submodule import: namespace pkg doesn't expose `firestore` attr via stubs
from google.cloud import bigquery

from config import settings
from libs.content_owner import derive_owner_from_filename

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("backfill_owners")


def _credentials() -> google.auth.compute_engine.Credentials:
    """Service-account credentials from the metadata server (fresh token)."""
    return google.auth.compute_engine.Credentials()


def _owner_case_sql() -> str:
    """Build a CASE expression mirroring derive_owner_from_filename, in config order.

    First matching slug wins. Substring match == SQL LIKE '%marker%' on a
    lower-cased filename. Unmatched rows keep their existing owner.
    """
    whens = []
    for slug, markers in settings.content_owners.items():
        conds = " OR ".join(f"LOWER(video_filename) LIKE '%{m.lower()}%'" for m in markers if m)
        if conds:
            whens.append(f"WHEN ({conds}) THEN '{slug}'")
    whens_sql = "\n      ".join(whens)
    return f"CASE\n      {whens_sql}\n      ELSE owner\n    END"


def backfill_bigquery(bq: bigquery.Client, table_ref: str, apply: bool) -> None:
    logger.info("\n=== BigQuery: %s ===", table_ref)
    if apply:
        bq.query(f"ALTER TABLE `{table_ref}` ADD COLUMN IF NOT EXISTS owner STRING").result()
        logger.info("  ALTER TABLE … ADD COLUMN IF NOT EXISTS owner STRING — done")
    else:
        logger.info("  [dry-run] would ALTER TABLE … ADD COLUMN IF NOT EXISTS owner STRING")

    # Preview the classification the UPDATE will apply.
    case_sql = _owner_case_sql()
    preview = f"""
        SELECT COALESCE(({case_sql}), 'UNTAGGED') AS owner, COUNT(*) AS n
        FROM `{table_ref}`
        WHERE owner IS NULL
        GROUP BY 1 ORDER BY 1
    """
    try:
        rows = list(bq.query(preview).result())
        if rows:
            logger.info("  Rows currently untagged, by filename-derived owner:")
            for r in rows:
                logger.info("    %-10s %d", r["owner"], r["n"])
        else:
            logger.info("  No untagged rows (owner already populated).")
    except Exception as e:  # column may not exist yet on a dry-run
        logger.info("  (could not preview — owner column likely not added yet: %s)", e)

    update = f"UPDATE `{table_ref}` SET owner = {case_sql} WHERE owner IS NULL"
    if apply:
        job = bq.query(update)
        job.result()
        logger.info("  UPDATE applied: %s rows touched", job.num_dml_affected_rows)
    else:
        logger.info("  [dry-run] would run UPDATE … SET owner = CASE(filename) WHERE owner IS NULL")


def backfill_firestore_videos(db: firestore.Client, apply: bool) -> None:
    col = db.collection(f"{settings.service_name}_videos")
    logger.info("\n=== Firestore: %s_videos ===", settings.service_name)
    changed = 0
    for doc in col.stream():
        data = doc.to_dict() or {}
        if (data.get("owner") or "").strip():
            continue  # already tagged (manual or prior run)
        owner = derive_owner_from_filename(data.get("filename", ""))
        if not owner:
            continue  # leave untagged (shared)
        changed += 1
        if apply:
            doc.reference.update({"owner": owner})
        logger.info("  %s %s -> owner=%s", "set" if apply else "[dry-run]", data.get("filename", doc.id), owner)
    logger.info("  %d video doc(s) %s", changed, "updated" if apply else "would be updated")


def tag_invite_codes(db: firestore.Client, overrides: dict, apply: bool) -> None:
    col = db.collection(f"{settings.service_name}_invite_codes")
    slugs = set(settings.content_owners.keys())
    logger.info("\n=== Firestore: %s_invite_codes ===", settings.service_name)
    changed = 0
    for doc in col.stream():
        data = doc.to_dict() or {}
        code, label = data.get("code", ""), (data.get("label") or "")
        # Resolve target owner: explicit override by code/id/label, else label==slug.
        target = overrides.get(code) or overrides.get(doc.id) or overrides.get(label)
        if not target and label.strip().lower() in slugs:
            target = label.strip().lower()
        if not target or data.get("owner") == target:
            continue
        changed += 1
        if apply:
            doc.reference.update({"owner": target})
        logger.info("  %s code=%s label=%r -> owner=%s", "set" if apply else "[dry-run]", code, label, target)
    if changed == 0:
        logger.info("  No invite codes matched. Pass --code-owner CODE=OWNER to tag explicitly.")
    else:
        logger.info("  %d invite code(s) %s", changed, "updated" if apply else "would be updated")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write changes (default: dry-run)")
    parser.add_argument(
        "--code-owner",
        action="append",
        default=[],
        metavar="CODE=OWNER",
        help="Tag an invite code (by code value, doc id, or label) with an owner slug. Repeatable.",
    )
    parser.add_argument("--skip-videos", action="store_true", help="Skip Firestore video stamping")
    parser.add_argument("--skip-codes", action="store_true", help="Skip invite-code tagging")
    args = parser.parse_args()

    overrides = {}
    for pair in args.code_owner:
        if "=" not in pair:
            logger.error("Bad --code-owner %r (expected CODE=OWNER)", pair)
            return 2
        k, v = pair.split("=", 1)
        overrides[k.strip()] = v.strip()

    mode = "APPLY" if args.apply else "DRY-RUN"
    logger.info("Backfill owners [%s] — project=%s, owners=%s", mode, settings.gcp_project_id, settings.content_owners)

    creds = _credentials()
    bq = bigquery.Client(project=settings.gcp_project_id, credentials=creds)
    db = firestore.Client(project=settings.gcp_project_id, database=settings.firestore_database, credentials=creds)
    table_ref = f"{settings.gcp_project_id}.{settings.bq_dataset}.scene_embeddings_v2"

    backfill_bigquery(bq, table_ref, args.apply)
    if not args.skip_videos:
        backfill_firestore_videos(db, args.apply)
    if not args.skip_codes:
        tag_invite_codes(db, overrides, args.apply)

    if not args.apply:
        logger.info("\nDry-run only. Re-run with --apply to write changes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
