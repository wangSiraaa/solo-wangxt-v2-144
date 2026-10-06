-- Evaluation schema. People (judges) and judgment-set versions are separate
-- concepts: a set version is an immutable bundle of qrels authored by judges.

CREATE TABLE IF NOT EXISTS judges (
    judge_id    TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    team        TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS judgment_sets (
    set_id      TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT,
    version     TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (name, version)
);

CREATE TABLE IF NOT EXISTS queries (
    query_id    TEXT PRIMARY KEY,
    text        TEXT NOT NULL,
    title       TEXT,
    scenario    TEXT,
    note        TEXT
);

-- Corpus metadata mirrored in Postgres so qrel UI rows can show document text
-- without querying OpenSearch.
CREATE TABLE IF NOT EXISTS corpus_docs (
    doc_id        TEXT PRIMARY KEY,
    canonical_id  TEXT NOT NULL,
    title         TEXT NOT NULL,
    body          TEXT NOT NULL,
    tags          TEXT[]
);
CREATE INDEX IF NOT EXISTS idx_corpus_canonical ON corpus_docs(canonical_id);

CREATE TABLE IF NOT EXISTS qrels (
    set_id      TEXT NOT NULL REFERENCES judgment_sets(set_id) ON DELETE CASCADE,
    query_id    TEXT NOT NULL REFERENCES queries(query_id) ON DELETE CASCADE,
    canonical_doc_id TEXT NOT NULL,
    grade       SMALLINT NOT NULL CHECK (grade BETWEEN 0 AND 3),
    judge_id    TEXT NOT NULL REFERENCES judges(judge_id),
    PRIMARY KEY (set_id, query_id, canonical_doc_id)
);
CREATE INDEX IF NOT EXISTS idx_qrels_query ON qrels(set_id, query_id);

CREATE TABLE IF NOT EXISTS run_configs (
    config_id   TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT,
    config      JSONB NOT NULL,           -- query-side configuration
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS experiments (
    experiment_id  TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    description    TEXT,
    judgment_set_id TEXT NOT NULL REFERENCES judgment_sets(set_id),
    treatment_config_id TEXT NOT NULL REFERENCES run_configs(config_id),
    baseline_config_id  TEXT REFERENCES run_configs(config_id),
    index_name     TEXT NOT NULL,         -- the bound index
    index_settings_snapshot JSONB,        -- frozen for reproducibility
    index_mapping_snapshot  JSONB,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- A run is the result of executing one query configuration against the bound
-- index. role: 'baseline' | 'treatment'.
CREATE TABLE IF NOT EXISTS runs (
    experiment_id TEXT NOT NULL REFERENCES experiments(experiment_id) ON DELETE CASCADE,
    config_id   TEXT NOT NULL REFERENCES run_configs(config_id),
    role        TEXT NOT NULL CHECK (role IN ('baseline','treatment')),
    index_name  TEXT NOT NULL,
    run_config_snapshot JSONB NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (experiment_id, role)
);

CREATE TABLE IF NOT EXISTS run_rankings (
    experiment_id TEXT NOT NULL,
    role          TEXT NOT NULL,
    query_id      TEXT NOT NULL,
    rank          INTEGER NOT NULL,       -- rank within deduped ranking
    raw_rank      INTEGER,                -- rank as returned by OpenSearch
    doc_id        TEXT NOT NULL,
    canonical_doc_id TEXT NOT NULL,
    score         DOUBLE PRECISION NOT NULL,
    tied          BOOLEAN NOT NULL DEFAULT false,
    duplicate     BOOLEAN NOT NULL DEFAULT false,
    PRIMARY KEY (experiment_id, role, query_id, rank),
    FOREIGN KEY (experiment_id, role) REFERENCES runs(experiment_id, role) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS run_metrics (
    experiment_id TEXT NOT NULL,
    role          TEXT NOT NULL,
    query_id      TEXT NOT NULL,
    ndcg_at_10        DOUBLE PRECISION,  -- NULL when undefined (0 relevant)
    mrr_at_10         DOUBLE PRECISION,
    recall_at_100     DOUBLE PRECISION,
    judged_at_10      DOUBLE PRECISION,
    ndcg_raw_zero_rel DOUBLE PRECISION,
    mrr_raw_zero_rel  DOUBLE PRECISION,
    recall_raw_zero_rel DOUBLE PRECISION,
    num_relevant      INTEGER,
    num_returned      INTEGER,
    duplicates_dropped INTEGER,
    PRIMARY KEY (experiment_id, role, query_id),
    FOREIGN KEY (experiment_id, role) REFERENCES runs(experiment_id, role) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS run_metrics_aggregate (
    experiment_id TEXT NOT NULL,
    role          TEXT NOT NULL,
    ndcg_at_10        DOUBLE PRECISION,
    mrr_at_10         DOUBLE PRECISION,
    recall_at_100     DOUBLE PRECISION,
    judged_at_10      DOUBLE PRECISION,
    num_queries            INTEGER,
    num_zero_relevant      INTEGER,
    num_missing_run        INTEGER,
    num_duplicates_dropped INTEGER,
    PRIMARY KEY (experiment_id, role),
    FOREIGN KEY (experiment_id, role) REFERENCES runs(experiment_id, role) ON DELETE CASCADE
);
