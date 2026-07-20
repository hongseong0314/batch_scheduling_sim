-- Production Data Backbone V1
-- PostgreSQL target schema for canonical ingestion, action proposal, and job audit data.

CREATE TABLE IF NOT EXISTS raw_source_records (
  record_id TEXT NOT NULL PRIMARY KEY,
  run_id TEXT NOT NULL,
  source_system TEXT NOT NULL,
  source_table TEXT NOT NULL,
  source_pk TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  operation_id TEXT NOT NULL DEFAULT '',
  equipment_id TEXT NOT NULL DEFAULT '',
  lot_id TEXT NOT NULL DEFAULT '',
  unit_id TEXT NOT NULL DEFAULT '',
  recipe_id TEXT NOT NULL DEFAULT '',
  event_time BIGINT,
  ingest_time BIGINT,
  decision_time BIGINT,
  schema_version TEXT NOT NULL,
  status TEXT NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS canonical_ingestion_records (
  record_id TEXT NOT NULL PRIMARY KEY,
  run_id TEXT NOT NULL,
  raw_record_id TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  canonical_id TEXT NOT NULL,
  canonical_namespace TEXT NOT NULL,
  operation_id TEXT NOT NULL DEFAULT '',
  equipment_id TEXT NOT NULL DEFAULT '',
  lot_id TEXT NOT NULL DEFAULT '',
  unit_id TEXT NOT NULL DEFAULT '',
  recipe_id TEXT NOT NULL DEFAULT '',
  event_type TEXT NOT NULL DEFAULT '',
  event_time BIGINT,
  ingest_time BIGINT,
  decision_time BIGINT,
  attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
  measurements JSONB NOT NULL DEFAULT '{}'::jsonb,
  quality_result JSONB NOT NULL DEFAULT '{}'::jsonb,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  schema_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_key_mappings (
  mapping_id TEXT NOT NULL PRIMARY KEY,
  run_id TEXT NOT NULL,
  source_system TEXT NOT NULL,
  source_table TEXT NOT NULL,
  source_pk TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  canonical_namespace TEXT NOT NULL,
  canonical_id TEXT NOT NULL,
  status TEXT NOT NULL,
  event_time BIGINT,
  ingest_time BIGINT,
  decision_time BIGINT,
  source_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS action_proposals (
  proposal_id TEXT NOT NULL PRIMARY KEY,
  run_id TEXT NOT NULL,
  correlation_id TEXT NOT NULL,
  proposal_type TEXT NOT NULL,
  status TEXT NOT NULL,
  direct_equipment_control BOOLEAN NOT NULL,
  decision_time BIGINT,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS action_proposal_reviews (
  review_id TEXT NOT NULL PRIMARY KEY,
  proposal_id TEXT NOT NULL,
  run_id TEXT NOT NULL,
  correlation_id TEXT NOT NULL,
  review_status TEXT NOT NULL,
  reviewer_id TEXT NOT NULL DEFAULT '',
  reviewed_at BIGINT,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS legacy_decisions (
  decision_id TEXT NOT NULL PRIMARY KEY,
  proposal_id TEXT NOT NULL,
  run_id TEXT NOT NULL,
  correlation_id TEXT NOT NULL,
  legacy_status TEXT NOT NULL,
  decision_time BIGINT,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS outcome_records (
  outcome_id TEXT NOT NULL PRIMARY KEY,
  proposal_id TEXT NOT NULL,
  run_id TEXT NOT NULL,
  correlation_id TEXT NOT NULL,
  outcome_status TEXT NOT NULL,
  event_time BIGINT,
  ingest_time BIGINT,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS ingestion_job_runs (
  job_run_id TEXT NOT NULL PRIMARY KEY,
  job_id TEXT NOT NULL,
  run_id TEXT NOT NULL,
  adapter_id TEXT NOT NULL,
  mode TEXT NOT NULL,
  status TEXT NOT NULL,
  window_start BIGINT,
  window_end BIGINT,
  raw_count INTEGER NOT NULL DEFAULT 0,
  canonical_count INTEGER NOT NULL DEFAULT 0,
  error_count INTEGER NOT NULL DEFAULT 0,
  started_at BIGINT,
  finished_at BIGINT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_raw_source_records_source_key
  ON raw_source_records (run_id, source_system, source_table, source_pk, entity_type);
CREATE INDEX IF NOT EXISTS idx_canonical_ingestion_entity
  ON canonical_ingestion_records (run_id, entity_type, canonical_id);
CREATE INDEX IF NOT EXISTS idx_canonical_ingestion_time
  ON canonical_ingestion_records (run_id, event_time, ingest_time);
CREATE INDEX IF NOT EXISTS idx_source_key_mappings_lookup
  ON source_key_mappings (run_id, source_system, source_table, source_pk, entity_type);
CREATE INDEX IF NOT EXISTS idx_action_proposals_correlation
  ON action_proposals (run_id, correlation_id, status);
CREATE INDEX IF NOT EXISTS idx_ingestion_job_runs_adapter
  ON ingestion_job_runs (run_id, adapter_id, status);
