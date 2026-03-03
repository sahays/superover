"""BigQuery client singleton for natural language search (AI.SEARCH).

Follows the existing get_db() / get_storage() singleton pattern.
Uses DML INSERT (not streaming API) to trigger autonomous embedding
generation. Embeddings are generated asynchronously by BigQuery after insert.
"""

import logging
from functools import lru_cache
from typing import Optional

from google.cloud import bigquery

from config import get_settings

logger = logging.getLogger(__name__)


class BigQueryClient:
    """Client for BigQuery scene embedding search operations."""

    def __init__(self):
        settings = get_settings()
        self.client = bigquery.Client(project=settings.gcp_project_id)
        self.dataset = settings.bq_dataset
        self.table_ref = f"{self.client.project}.{self.dataset}.scene_embeddings"
        logger.info(
            f"BigQuery client initialized: project={self.client.project}, "
            f"dataset={self.dataset}, table={self.table_ref}"
        )

    def sync_scene_result(
        self,
        result_id: str,
        video_id: str,
        video_filename: Optional[str],
        scene_job_id: Optional[str],
        chunk_index: Optional[int],
        text_content: str,
        timestamp_start: Optional[str],
        timestamp_end: Optional[str],
    ) -> None:
        """Insert a scene result via DML INSERT. Returns immediately.

        Embeddings are generated asynchronously by BigQuery's AI.EMBED.
        Use check_embedding_statuses() to poll for completion later.
        """
        logger.info(f"Syncing result {result_id} for video {video_id} (text_content length: {len(text_content)})")

        sql = f"""
        INSERT INTO `{self.table_ref}`
            (result_id, video_id, video_filename, scene_job_id,
             chunk_index, text_content, timestamp_start, timestamp_end)
        VALUES
            (@result_id, @video_id, @video_filename, @scene_job_id,
             @chunk_index, @text_content, @timestamp_start, @timestamp_end)
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("result_id", "STRING", result_id),
                bigquery.ScalarQueryParameter("video_id", "STRING", video_id),
                bigquery.ScalarQueryParameter("video_filename", "STRING", video_filename),
                bigquery.ScalarQueryParameter("scene_job_id", "STRING", scene_job_id),
                bigquery.ScalarQueryParameter("chunk_index", "INT64", chunk_index),
                bigquery.ScalarQueryParameter("text_content", "STRING", text_content),
                bigquery.ScalarQueryParameter("timestamp_start", "STRING", timestamp_start),
                bigquery.ScalarQueryParameter("timestamp_end", "STRING", timestamp_end),
            ]
        )
        job = self.client.query(sql, job_config=job_config)
        job.result()  # Wait for DML to complete
        logger.info(f"DML INSERT complete for result {result_id}, job_id={job.job_id}")

    def check_embedding_statuses(self, result_ids: list[str]) -> dict[str, str]:
        """Check embedding status for multiple result_ids in a single query.

        Returns a dict mapping result_id -> status:
          "ready"   — embedding generated successfully
          "pending" — row exists, embedding not yet generated
          "error"   — embedding generation failed (status message present)
          (missing) — result_id not found in BigQuery
        """
        if not result_ids:
            return {}

        sql = f"""
        SELECT
            result_id,
            text_embedding.status AS embed_status,
            ARRAY_LENGTH(text_embedding.result) AS embed_dim
        FROM `{self.table_ref}`
        WHERE result_id IN UNNEST(@result_ids)
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ArrayQueryParameter("result_ids", "STRING", result_ids),
            ]
        )

        statuses: dict[str, str] = {}
        try:
            rows = list(self.client.query(sql, job_config=job_config).result())
            for row in rows:
                rid = row.result_id
                embed_status = row.embed_status
                embed_dim = row.embed_dim

                if embed_dim is not None and embed_dim > 0:
                    if embed_status is None or embed_status == "":
                        statuses[rid] = "ready"
                    else:
                        statuses[rid] = "error"
                        logger.error(f"Embedding error for {rid}: status='{embed_status}', dims={embed_dim}")
                elif embed_status is not None and embed_status != "":
                    statuses[rid] = "error"
                    logger.error(f"Embedding error for {rid}: status='{embed_status}'")
                else:
                    statuses[rid] = "pending"

            logger.info(
                f"Checked {len(result_ids)} embedding statuses: "
                f"{sum(1 for s in statuses.values() if s == 'ready')} ready, "
                f"{sum(1 for s in statuses.values() if s == 'pending')} pending, "
                f"{sum(1 for s in statuses.values() if s == 'error')} error"
            )
        except Exception as e:
            logger.error(f"Failed to check embedding statuses: {e}")
            # Return all as pending so we retry next time
            for rid in result_ids:
                statuses[rid] = "pending"

        return statuses

    def search_videos(self, query: str, limit: int = 20) -> list[dict]:
        """Cross-video semantic search using AI.SEARCH."""
        logger.info(f"Search videos: query='{query}', limit={limit}")
        sql = f"""
        SELECT base.video_id, base.video_filename, base.text_content,
               base.chunk_index, base.timestamp_start, base.timestamp_end,
               distance
        FROM AI.SEARCH(
            TABLE `{self.table_ref}`,
            'text_content',
            @query,
            top_k => @limit
        )
        ORDER BY distance ASC
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("query", "STRING", query),
                bigquery.ScalarQueryParameter("limit", "INT64", limit),
            ]
        )
        results = [dict(row) for row in self.client.query(sql, job_config=job_config).result()]
        logger.info(f"Search videos returned {len(results)} results")
        return results

    def search_within_video(self, video_id: str, query: str, limit: int = 20) -> list[dict]:
        """In-video semantic search. Pre-filters by video_id."""
        logger.info(f"Search within video: video_id={video_id}, query='{query}', limit={limit}")
        sql = f"""
        SELECT base.*, distance
        FROM AI.SEARCH(
            (SELECT * FROM `{self.table_ref}` WHERE video_id = @video_id),
            'text_content',
            @query,
            top_k => @limit
        )
        ORDER BY distance ASC
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("video_id", "STRING", video_id),
                bigquery.ScalarQueryParameter("query", "STRING", query),
                bigquery.ScalarQueryParameter("limit", "INT64", limit),
            ]
        )
        results = [dict(row) for row in self.client.query(sql, job_config=job_config).result()]
        logger.info(f"Search within video {video_id} returned {len(results)} results")
        return results

    def get_synced_result_ids(self) -> set[str]:
        """Return set of result_ids already in BigQuery."""
        sql = f"SELECT result_id FROM `{self.table_ref}`"
        ids = {row.result_id for row in self.client.query(sql).result()}
        logger.info(f"Found {len(ids)} synced result IDs in BigQuery")
        return ids

    def delete_synced_result(self, result_id: str) -> None:
        """Remove a synced result from BigQuery."""
        logger.info(f"Deleting synced result {result_id} from BigQuery")
        sql = f"DELETE FROM `{self.table_ref}` WHERE result_id = @result_id"
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("result_id", "STRING", result_id),
            ]
        )
        self.client.query(sql, job_config=job_config).result()
        logger.info(f"Deleted result {result_id} from BigQuery")


@lru_cache(maxsize=1)
def get_bq_client() -> BigQueryClient:
    """Get cached BigQuery client singleton."""
    return BigQueryClient()
