#!/usr/bin/env python3
"""Migrate the search index from BigQuery (scene_embeddings_v2) to Bigtable.

Reads every row from the BQ table, re-embeds text_content with the Gemini
embeddings API (settings.embedding_model — vectors are NOT portable across
embedding models, so the BQ AI.EMBED/text-embedding-005 vectors are discarded),
and writes rows to the Bigtable table. Idempotent: rows whose result_id
already exists in Bigtable are skipped (use --force to rewrite them).

One-time infra setup (1-node SSD cluster — ~$475/month minimum, sized for a
small demo corpus; the API service account needs roles/bigtable.user):

    gcloud services enable bigtableadmin.googleapis.com bigtable.googleapis.com
    gcloud bigtable instances create superover-search \
        --display-name="Superover Search" \
        --cluster-config=id=superover-search-c1,zone=asia-south1-a,nodes=1
    python scripts/migrate_bq_to_bigtable.py --create-table

Then run the migration and flip the backend:

    python scripts/migrate_bq_to_bigtable.py
    # .env / Cloud Run env: SEARCH_BACKEND=bigtable
    # (retune SEARCH_DISPLAY_MAX_DISTANCE for gemini-embedding-001 — see --stats)

Rollback: set SEARCH_BACKEND=bigquery; the BQ table is left untouched.
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import get_settings  # noqa: E402
from libs.bigquery import get_bq_client  # noqa: E402
from libs.bigtable import get_bt_client  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("migrate_bq_to_bigtable")


def create_table() -> None:
    """Create the Bigtable table + column family via the admin API."""
    from google.cloud import bigtable
    from google.cloud.bigtable import column_family

    settings = get_settings()
    admin = bigtable.Client(project=settings.gcp_project_id, admin=True)
    instance = admin.instance(settings.bt_instance)
    table = instance.table(settings.bt_table)
    if table.exists():
        logger.info("Table %s already exists", settings.bt_table)
        return
    table.create(column_families={"d": column_family.MaxVersionsGCRule(1)})
    logger.info("Created table %s in instance %s", settings.bt_table, settings.bt_instance)


def migrate(force: bool = False, limit: int | None = None) -> None:
    bq = get_bq_client()
    bt = get_bt_client()

    sql = f"""
    SELECT result_id, video_id, video_filename, scene_job_id, chunk_index,
           text_content, timestamp_start, timestamp_end, result_data_json,
           gcs_path, owner
    FROM `{bq.table_ref}`
    """
    rows = [dict(r) for r in bq.client.query(sql).result()]
    logger.info("BigQuery source rows: %d", len(rows))

    existing = set() if force else bt.get_synced_result_ids()
    if existing:
        logger.info("Bigtable already has %d row(s); skipping those (use --force to rewrite)", len(existing))

    migrated = skipped = failed = 0
    for row in rows[:limit] if limit else rows:
        rid = row["result_id"]
        if rid in existing:
            skipped += 1
            continue
        try:
            bt.sync_scene_result(
                result_id=rid,
                video_id=row.get("video_id", ""),
                video_filename=row.get("video_filename"),
                scene_job_id=row.get("scene_job_id"),
                chunk_index=row.get("chunk_index"),
                text_content=row.get("text_content") or "",
                timestamp_start=row.get("timestamp_start"),
                timestamp_end=row.get("timestamp_end"),
                result_data_json=row.get("result_data_json"),
                gcs_path=row.get("gcs_path"),
                owner=row.get("owner"),
            )
            migrated += 1
        except Exception as e:
            failed += 1
            logger.error("Failed to migrate %s: %s", rid, e)

    logger.info(
        "Migration done: %d migrated, %d skipped (already present), %d failed, %d total",
        migrated,
        skipped,
        failed,
        len(rows),
    )
    if failed:
        sys.exit(1)


def stats(queries: list[str]) -> None:
    """Print distance distributions for sample queries — use this to tune
    SEARCH_DISPLAY_MAX_DISTANCE for the new embedding model."""
    bt = get_bt_client()
    for q in queries:
        rows = bt.search_videos(q, limit=20)
        dists = [f"{r['distance']:.3f}" for r in rows]
        print(f"query={q!r}: n={len(rows)} distances={dists}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--create-table", action="store_true", help="Create the Bigtable table and exit")
    parser.add_argument("--force", action="store_true", help="Rewrite rows that already exist in Bigtable")
    parser.add_argument("--limit", type=int, default=None, help="Migrate at most N rows (smoke test)")
    parser.add_argument(
        "--stats",
        nargs="+",
        metavar="QUERY",
        help="Print distance distributions for sample queries (threshold tuning) and exit",
    )
    args = parser.parse_args()

    if args.create_table:
        create_table()
        return
    try:
        if args.stats:
            stats(args.stats)
        else:
            migrate(force=args.force, limit=args.limit)
    finally:
        # The sync Bigtable data client's event-loop thread is non-daemon;
        # without close() the script never exits.
        get_bt_client().close()


if __name__ == "__main__":
    main()
