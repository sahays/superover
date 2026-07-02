"""Unit tests for libs/bigtable/client.py — mocked data client + embedder."""

import struct
from unittest.mock import MagicMock, patch

import pytest

from libs.bigtable.client import BigtableClient, floats_to_bytes


def _fake_row(values: dict) -> MagicMock:
    """execute_query rows support __getitem__ by column alias."""
    row = MagicMock()
    row.__getitem__.side_effect = lambda k: values[k]
    return row


@pytest.fixture
def bt():
    with (
        patch("libs.bigtable.client.BigtableDataClient") as mock_client_cls,
        patch("libs.bigtable.client.get_text_embedder") as mock_get_embedder,
    ):
        embedder = MagicMock()
        embedder.embed.return_value = [0.6, 0.8]
        mock_get_embedder.return_value = embedder
        client = BigtableClient()
        client.mock_data_client = mock_client_cls.return_value
        client.mock_table = mock_client_cls.return_value.get_table.return_value
        yield client


@pytest.mark.unit
class TestFloatsToBytes:
    def test_big_endian_float32(self):
        encoded = floats_to_bytes([1.5, -2.0])
        assert encoded == struct.pack(">2f", 1.5, -2.0)
        assert len(encoded) == 8


@pytest.mark.unit
class TestSync:
    def test_sync_embeds_and_writes_row(self, bt):
        bt.sync_scene_result(
            result_id="r1",
            video_id="v1",
            video_filename="clip.mp4",
            scene_job_id="j1",
            chunk_index=2,
            text_content="a tense courtroom scene",
            timestamp_start="00:00:07",
            timestamp_end="00:00:44",
            result_data_json='{"genre": "drama"}',
            gcs_path="gs://b/clip.mp4",
            owner="sony",
        )
        bt.embedder.embed.assert_called_once_with("a tense courtroom scene")
        row_key, mutations = bt.mock_table.mutate_row.call_args.args
        assert row_key == "r1"
        cells = {m.qualifier if isinstance(m.qualifier, str) else m.qualifier.decode(): m for m in mutations}
        assert cells["embedding"].new_value == floats_to_bytes([0.6, 0.8])
        assert cells["chunk_index"].new_value == b"2"
        assert cells["owner"].new_value == b"sony"

    def test_sync_omits_null_owner_cell(self, bt):
        bt.sync_scene_result(
            result_id="r1",
            video_id="v1",
            video_filename=None,
            scene_job_id=None,
            chunk_index=None,
            text_content="text",
            timestamp_start=None,
            timestamp_end=None,
            owner=None,
        )
        _, mutations = bt.mock_table.mutate_row.call_args.args
        qualifiers = {m.qualifier if isinstance(m.qualifier, str) else m.qualifier.decode() for m in mutations}
        assert "owner" not in qualifiers

    def test_sync_accepts_precomputed_embedding(self, bt):
        bt.sync_scene_result(
            result_id="r1",
            video_id="v1",
            video_filename=None,
            scene_job_id=None,
            chunk_index=None,
            text_content="text",
            timestamp_start=None,
            timestamp_end=None,
            embedding=[0.0, 1.0],
        )
        bt.embedder.embed.assert_not_called()

    def test_sync_fans_out_scene_rows_with_clip_times(self, bt):
        result_data = {
            "genre": "Drama",
            "scenes": [
                {
                    "start_time": "00:00:05.000",
                    "end_time": "00:00:31.500",
                    "summary": "A tense courtroom exchange",
                    "people": [{"label": "Judge Rao"}],
                },
                {"summary": "untimed scene, skipped"},
            ],
        }
        bt.sync_scene_result(
            result_id="r1",
            video_id="v1",
            video_filename="clip.mp4",
            scene_job_id=None,
            chunk_index=None,
            text_content="whole video text",
            timestamp_start=None,
            timestamp_end=None,
            result_data_json=__import__("json").dumps(result_data),
        )
        calls = bt.mock_table.mutate_row.call_args_list
        assert len(calls) == 2  # base row + 1 timed scene row
        assert calls[0].args[0] == "r1"
        scene_key, scene_mutations = calls[1].args
        assert scene_key == "r1#s0"
        cells = {m.qualifier if isinstance(m.qualifier, str) else m.qualifier.decode(): m for m in scene_mutations}
        assert cells["timestamp_start"].new_value == b"00:00:05"
        assert cells["timestamp_end"].new_value == b"00:00:31"
        scene_text = cells["text_content"].new_value.decode()
        assert "courtroom" in scene_text and "Judge Rao" in scene_text and "Drama" in scene_text


@pytest.mark.unit
class TestSearch:
    def _result_row(self):
        return _fake_row(
            {
                "result_id": b"r1",
                "video_id": b"v1",
                "video_filename": b"clip.mp4",
                "scene_job_id": b"j1",
                "text_content": b"scene text",
                "timestamp_start": b"00:00:07",
                "timestamp_end": b"00:00:44",
                "result_data_json": b"{}",
                "gcs_path": b"gs://b/clip.mp4",
                "chunk_index": b"2",
                "distance": 0.42,
            }
        )

    def test_search_videos_normalizes_rows(self, bt):
        bt.mock_data_client.execute_query.return_value = iter([self._result_row()])
        results = bt.search_videos("courtroom drama", limit=5)

        bt.embedder.embed.assert_called_once_with("courtroom drama", for_query=True)
        (sql, instance_id), kwargs = bt.mock_data_client.execute_query.call_args
        assert "COSINE_DISTANCE(TO_VECTOR32(d['embedding']), TO_VECTOR32(@qvec))" in sql
        assert "WHERE" not in sql  # no owner scope
        assert "LIMIT 5" in sql
        assert kwargs["parameters"]["qvec"] == floats_to_bytes([0.6, 0.8])

        assert results == [
            {
                "result_id": "r1",
                "video_id": "v1",
                "video_filename": "clip.mp4",
                "scene_job_id": "j1",
                "text_content": "scene text",
                "timestamp_start": "00:00:07",
                "timestamp_end": "00:00:44",
                "result_data_json": "{}",
                "gcs_path": "gs://b/clip.mp4",
                "chunk_index": 2,
                "distance": 0.42,
            }
        ]

    def test_search_videos_owner_scoped(self, bt):
        bt.mock_data_client.execute_query.return_value = iter([])
        bt.search_videos("query", owner="zee")
        (sql, _), kwargs = bt.mock_data_client.execute_query.call_args
        assert "CAST(d['owner'] AS STRING) = @owner OR d['owner'] IS NULL" in sql
        assert kwargs["parameters"]["owner"] == "zee"

    def test_search_within_video_filters_video_and_owner(self, bt):
        bt.mock_data_client.execute_query.return_value = iter([])
        bt.search_within_video("v9", "query", owner="sony")
        (sql, _), kwargs = bt.mock_data_client.execute_query.call_args
        assert "CAST(d['video_id'] AS STRING) = @video_id" in sql
        assert "d['owner'] IS NULL" in sql
        assert kwargs["parameters"]["video_id"] == "v9"


@pytest.mark.unit
class TestHousekeeping:
    def test_check_embedding_statuses_present_rows_are_ready(self, bt):
        bt.mock_data_client.execute_query.return_value = iter(
            [_fake_row({"result_id": b"r1"}), _fake_row({"result_id": b"r2"})]
        )
        statuses = bt.check_embedding_statuses(["r1", "r2", "missing"])
        assert statuses == {"r1": "ready", "r2": "ready"}

    def test_synced_ids_collapse_scene_rows(self, bt):
        bt.mock_data_client.execute_query.return_value = iter(
            [_fake_row({"result_id": b"r1"}), _fake_row({"result_id": b"r1#s0"}), _fake_row({"result_id": b"r1#s1"})]
        )
        assert bt.get_synced_result_ids() == {"r1"}

    def test_delete_removes_base_and_scene_rows(self, bt):
        bt.mock_data_client.execute_query.return_value = iter(
            [_fake_row({"row_key": b"r1"}), _fake_row({"row_key": b"r1#s0"})]
        )
        bt.delete_synced_result("r1")
        deleted = [c.args[0] for c in bt.mock_table.mutate_row.call_args_list]
        assert deleted == ["r1", "r1#s0"]
        assert all(type(c.args[1][0]).__name__ == "DeleteAllFromRow" for c in bt.mock_table.mutate_row.call_args_list)
