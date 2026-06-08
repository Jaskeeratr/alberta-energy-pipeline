CREATE TABLE IF NOT EXISTS oil_production (
    id              SERIAL PRIMARY KEY,
    field_name      VARCHAR(200),
    operator        VARCHAR(200),
    production_date DATE,
    volume_m3       NUMERIC(15, 2),
    province        VARCHAR(10) DEFAULT 'AB',
    loaded_at       TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_oil_field ON oil_production(field_name);
CREATE INDEX idx_oil_date  ON oil_production(production_date);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id          SERIAL PRIMARY KEY,
    source_name     VARCHAR(100) NOT NULL,
    started_at      TIMESTAMP DEFAULT NOW(),
    finished_at     TIMESTAMP,
    status          VARCHAR(20) NOT NULL DEFAULT 'running',
    rows_extracted  INTEGER DEFAULT 0,
    rows_loaded     INTEGER DEFAULT 0,
    rows_rejected   INTEGER DEFAULT 0,
    error_rate      NUMERIC(8, 4) DEFAULT 0,
    error_message   TEXT
);

CREATE TABLE IF NOT EXISTS data_quality_issues (
    issue_id        SERIAL PRIMARY KEY,
    pipeline_run_id INTEGER REFERENCES pipeline_runs(run_id) ON DELETE CASCADE,
    source_name     VARCHAR(100) NOT NULL,
    row_identifier  VARCHAR(100),
    issue_type      VARCHAR(100) NOT NULL,
    issue_detail    TEXT,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_pipeline_runs_source ON pipeline_runs(source_name);
CREATE INDEX idx_pipeline_runs_status ON pipeline_runs(status);
CREATE INDEX idx_quality_issues_run ON data_quality_issues(pipeline_run_id);
