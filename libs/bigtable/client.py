"""Bigtable client singleton for natural language search (KNN vector search).

Drop-in alternative to libs/bigquery/client.py (same method surface), selected
by settings.search_backend. Embeddings are generated explicitly via the Gemini
embeddings API (libs/gemini/embeddings.py) — at sync time for documents and at
query time for searches — and stored as big-endian float32 bytes, the encoding
Bigtable's TO_VECTOR32 expects. Searches run GoogleSQL KNN
(COSINE_DISTANCE + ORDER BY + LIMIT) via execute_query, which returns in tens
of milliseconds versus BigQuery's ~1.4s job overhead.

Row key = result_id (searches are full scans over this small table anyway, so
no key-prefix scoping is needed; owner/video filters are SQL WHERE clauses).
"""

import json
import logging
import struct
from functools import lru_cache
from typing import Any, Optional

from google.cloud.bigtable.data import BigtableDataClient, SetCell

from config import get_settings
from libs.gemini.embeddings import get_text_embedder
from libs.scene_clips import build_scene_text, extract_scene_entries

# Scene rows are keyed "{result_id}#s{i}". The base (whole-video) row keeps
# the bare result_id key; housekeeping treats the set as one logical result.
SCENE_KEY_SEP = "#s"

logger = logging.getLogger(__name__)

COLUMN_FAMILY = "d"

# Columns mirrored from the BigQuery scene_embeddings_v2 schema.
_STRING_COLUMNS = (
    "result_id",
    "video_id",
    "video_filename",
    "scene_job_id",
    "text_content",
    "timestamp_start",
    "timestamp_end",
    "result_data_json",
    "gcs_path",
    "owner",
)

_SELECT_COLUMNS = ", ".join(
    f"CAST(d['{col}'] AS STRING) AS {col}" for col in _STRING_COLUMNS + ("chunk_index",) if col != "owner"
)


def floats_to_bytes(values: list[float]) -> bytes:
    """Serialize a vector as big-endian IEEE-754 float32 (TO_VECTOR32 format)."""
    return struct.pack(f">{len(values)}f", *values)


def _decode(value: Any) -> Any:
    """Bigtable SQL returns cell values as bytes; decode to str where needed."""
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return value


class BigtableClient:
    """Client for Bigtable scene embedding search operations."""

    def __init__(self):
        settings = get_settings()
        self.instance_id = settings.bt_instance
        self.table_id = settings.bt_table
        self.client = BigtableDataClient(project=settings.gcp_project_id)
        self.table = self.client.get_table(self.instance_id, self.table_id)
        self.embedder = get_text_embedder()
        logger.info(
            f"Bigtable client initialized: project={settings.gcp_project_id}, "
            f"instance={self.instance_id}, table={self.table_id}"
        )

    # === Sync (write) path ===

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
        result_data_json: Optional[str] = None,
        gcs_path: Optional[str] = None,
        owner: Optional[str] = None,
        embedding: Optional[list[float]] = None,
    ) -> None:
        """Embed and write one scene result. Searchable on return.

        Writes the whole-video row (key = result_id) plus one row per timed
        scene (key = result_id#s{i}) so KNN can retrieve the specific moment
        a query targets and ranking can emit `clip` recommendations — the
        clip localization the curator LLM used to do semantically.

        `embedding` lets callers supply a precomputed vector for the base
        row; scene rows always embed their own text here.
        """
        logger.info(f"Syncing result {result_id} for video {video_id} (text_content length: {len(text_content)})")
        vector = embedding or self.embedder.embed(text_content)
        self._write_row(
            row_key=result_id,
            values={
                "result_id": result_id,
                "video_id": video_id,
                "video_filename": video_filename,
                "scene_job_id": scene_job_id,
                "chunk_index": str(chunk_index) if chunk_index is not None else None,
                "text_content": text_content,
                "timestamp_start": timestamp_start,
                "timestamp_end": timestamp_end,
                "result_data_json": result_data_json,
                "gcs_path": gcs_path,
                "owner": owner or None,
            },
            vector=vector,
        )

        result_data: dict = {}
        if result_data_json:
            try:
                result_data = json.loads(result_data_json)
            except (json.JSONDecodeError, TypeError):
                result_data = {}
        entries = extract_scene_entries(result_data) if isinstance(result_data, dict) else []
        for i, entry in enumerate(entries):
            scene_text = build_scene_text(entry, result_data)
            self._write_row(
                row_key=f"{result_id}{SCENE_KEY_SEP}{i}",
                values={
                    "result_id": f"{result_id}{SCENE_KEY_SEP}{i}",
                    "video_id": video_id,
                    "video_filename": video_filename,
                    "scene_job_id": scene_job_id,
                    "chunk_index": str(i),
                    "text_content": scene_text,
                    "timestamp_start": entry["start"],
                    "timestamp_end": entry["end"],
                    "result_data_json": result_data_json,
                    "gcs_path": gcs_path,
                    "owner": owner or None,
                },
                vector=self.embedder.embed(scene_text),
            )
        logger.info(
            f"Bigtable write complete for result {result_id} ({len(vector)}-dim embedding, {len(entries)} scene row(s))"
        )

    def _write_row(self, row_key: str, values: dict[str, Optional[str]], vector: list[float]) -> None:
        mutations = [SetCell(COLUMN_FAMILY, col, val.encode("utf-8")) for col, val in values.items() if val is not None]
        mutations.append(SetCell(COLUMN_FAMILY, "embedding", floats_to_bytes(vector)))
        self.table.mutate_row(row_key, mutations)

    def check_embedding_statuses(self, result_ids: list[str]) -> dict[str, str]:
        """Embeddings are written synchronously — a present row is 'ready'."""
        if not result_ids:
            return {}
        synced = self.get_synced_result_ids()
        return {rid: "ready" for rid in result_ids if rid in synced}

    # === Search (read) path ===

    def search_videos(self, query: str, limit: int = 20, owner: Optional[str] = None) -> list[dict]:
        """Cross-video KNN search. Owner scoping matches the BQ client: a set
        owner sees its own rows plus untagged (shared) rows; falsy owner
        (master/operator) searches everything.
        """
        logger.info(f"Search videos: query='{query}', limit={limit}, owner={owner or '*'}")
        where = ""
        parameters: dict[str, Any] = {"qvec": floats_to_bytes(self.embedder.embed(query, for_query=True))}
        if owner:
            where = "WHERE (CAST(d['owner'] AS STRING) = @owner OR d['owner'] IS NULL)"
            parameters["owner"] = owner
        return self._knn_query(where, parameters, limit)

    def search_within_video(
        self, video_id: str, query: str, limit: int = 20, owner: Optional[str] = None
    ) -> list[dict]:
        """In-video KNN search. Owner scoping blocks cross-studio video_id guessing."""
        logger.info(f"Search within video: video_id={video_id}, query='{query}', limit={limit}, owner={owner or '*'}")
        where = "WHERE CAST(d['video_id'] AS STRING) = @video_id"
        parameters: dict[str, Any] = {
            "qvec": floats_to_bytes(self.embedder.embed(query, for_query=True)),
            "video_id": video_id,
        }
        if owner:
            where += " AND (CAST(d['owner'] AS STRING) = @owner OR d['owner'] IS NULL)"
            parameters["owner"] = owner
        return self._knn_query(where, parameters, limit)

    def _knn_query(self, where: str, parameters: dict[str, Any], limit: int) -> list[dict]:
        """Run the KNN query and normalize rows to the BQ client's dict shape."""
        sql = f"""
        SELECT {_SELECT_COLUMNS},
               COSINE_DISTANCE(TO_VECTOR32(d['embedding']), TO_VECTOR32(@qvec)) AS distance
        FROM `{self.table_id}`
        {where}
        ORDER BY distance ASC
        LIMIT {int(limit)}
        """
        results = []
        for row in self.client.execute_query(sql, self.instance_id, parameters=parameters):
            record = {col: _decode(row[col]) for col in _STRING_COLUMNS if col != "owner"}
            chunk_index = _decode(row["chunk_index"])
            record["chunk_index"] = int(chunk_index) if chunk_index is not None else None
            record["distance"] = row["distance"]
            results.append(record)
        logger.info(f"Bigtable KNN search returned {len(results)} results")
        return results

    # === Housekeeping ===

    def get_synced_result_ids(self) -> set[str]:
        """Return set of logical result_ids in Bigtable (scene-row keys are
        collapsed onto their base result_id)."""
        sql = f"SELECT CAST(_key AS STRING) AS result_id FROM `{self.table_id}`"
        ids = {
            _decode(row["result_id"]).split(SCENE_KEY_SEP, 1)[0]
            for row in self.client.execute_query(sql, self.instance_id)
        }
        logger.info(f"Found {len(ids)} synced result IDs in Bigtable")
        return ids

    def delete_synced_result(self, result_id: str) -> None:
        """Remove a synced result's base row and all its scene rows."""
        from google.cloud.bigtable.data import DeleteAllFromRow

        sql = f"""
        SELECT CAST(_key AS STRING) AS row_key FROM `{self.table_id}`
        WHERE CAST(_key AS STRING) = @rid
           OR STARTS_WITH(CAST(_key AS STRING), @scene_prefix)
        """
        params = {"rid": result_id, "scene_prefix": f"{result_id}{SCENE_KEY_SEP}"}
        keys = [_decode(row["row_key"]) for row in self.client.execute_query(sql, self.instance_id, parameters=params)]
        logger.info(f"Deleting synced result {result_id} from Bigtable ({len(keys)} row(s))")
        for key in keys:
            self.table.mutate_row(key, [DeleteAllFromRow()])

    def close(self) -> None:
        """Close the data client. Required for short-lived processes (scripts):
        the sync client's internal event-loop thread is non-daemon and keeps
        the process alive until closed. Long-lived services never call this."""
        self.client.close()


@lru_cache(maxsize=1)
def get_bt_client() -> BigtableClient:
    """Get cached Bigtable client singleton."""
    return BigtableClient()
