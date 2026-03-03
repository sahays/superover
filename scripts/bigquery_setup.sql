-- BigQuery setup for Natural Language Search (AI.SEARCH)
--
-- Prerequisites:
--   1. Enable Vertex AI API:
--      gcloud services enable aiplatform.googleapis.com
--   2. Create a BigQuery Cloud resource connection (or use default)
--   3. Grant the connection's service account the Vertex AI User role
--
-- Usage:
--   Replace PROJECT_ID and CONNECTION_ID with your values, then run:
--   bq query --use_legacy_sql=false < scripts/bigquery_setup.sql

-- 1. Create dataset
CREATE SCHEMA IF NOT EXISTS `PROJECT_ID.superover_search`;

-- 2. Create table with autonomous embedding generation
--    Embeddings auto-generate on INSERT via AI.EMBED
CREATE TABLE IF NOT EXISTS `PROJECT_ID.superover_search.scene_embeddings` (
  result_id STRING NOT NULL,
  video_id STRING NOT NULL,
  video_filename STRING,
  scene_job_id STRING,
  chunk_index INT64,
  text_content STRING NOT NULL,
  timestamp_start STRING,
  timestamp_end STRING,
  synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  text_embedding STRUCT<result ARRAY<FLOAT64>, status STRING>
    GENERATED ALWAYS AS (
      AI.EMBED(
        text_content,
        connection_id => 'CONNECTION_ID',
        endpoint => 'text-embedding-005'
      )
    )
    STORED OPTIONS (asynchronous = TRUE)
);

-- 3. V2 table with full analysis JSON and GCS path for Firestore-free search
CREATE TABLE IF NOT EXISTS `PROJECT_ID.superover_search.scene_embeddings_v2` (
  result_id STRING NOT NULL,
  video_id STRING NOT NULL,
  video_filename STRING,
  scene_job_id STRING,
  chunk_index INT64,
  text_content STRING NOT NULL,
  timestamp_start STRING,
  timestamp_end STRING,
  result_data_json STRING,
  gcs_path STRING,
  synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  text_embedding STRUCT<result ARRAY<FLOAT64>, status STRING>
    GENERATED ALWAYS AS (
      AI.EMBED(
        text_content,
        connection_id => 'CONNECTION_ID',
        endpoint => 'text-embedding-005'
      )
    )
    STORED OPTIONS (asynchronous = TRUE)
);

-- 4. Create vector index (optional, improves perf at scale; needs 3+ rows)
-- Uncomment after inserting at least 3 rows:
-- CREATE VECTOR INDEX IF NOT EXISTS scene_embedding_idx
--   ON `PROJECT_ID.superover_search.scene_embeddings_v2`(text_embedding)
--   OPTIONS (index_type = 'IVF');
