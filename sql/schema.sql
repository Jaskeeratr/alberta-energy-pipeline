CREATE TABLE IF NOT EXISTS oil_production (
    id              SERIAL PRIMARY KEY,
    field_name      VARCHAR(200),
    operator        VARCHAR(200),
    production_date DATE,
    volume_m3       NUMERIC(15, 2),
    province        VARCHAR(10) DEFAULT 'AB',
    loaded_at       TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_oil_field ON oil_production(field_name);
CREATE INDEX IF NOT EXISTS idx_oil_date  ON oil_production(production_date);

-- Natural key used by the incremental upsert in scripts/load.py.
CREATE UNIQUE INDEX IF NOT EXISTS uq_oil_production_record
    ON oil_production(field_name, operator, production_date);

CREATE TABLE IF NOT EXISTS gas_production (
    id              SERIAL PRIMARY KEY,
    field_name      VARCHAR(200),
    operator        VARCHAR(200),
    production_date DATE,
    volume_m3       NUMERIC(15, 2),
    province        VARCHAR(10) DEFAULT 'AB',
    loaded_at       TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gas_field ON gas_production(field_name);
CREATE INDEX IF NOT EXISTS idx_gas_date  ON gas_production(production_date);

-- Natural key used by the incremental upsert in scripts/load.py.
CREATE UNIQUE INDEX IF NOT EXISTS uq_gas_production_record
    ON gas_production(field_name, operator, production_date);

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

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_source ON pipeline_runs(source_name);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status ON pipeline_runs(status);
CREATE INDEX IF NOT EXISTS idx_quality_issues_run ON data_quality_issues(pipeline_run_id);

-- Petrinex Alberta monthly conventional volumetric data.
-- Roughly 520,000 rows per production month, so this table is sized and
-- indexed for bulk loading rather than the small AER summary tables above.
CREATE TABLE IF NOT EXISTS facility_production (
    id                    BIGSERIAL PRIMARY KEY,
    production_month      DATE NOT NULL,
    operator_ba_id        VARCHAR(20),
    operator_name         VARCHAR(200),
    facility_id           VARCHAR(30) NOT NULL,
    facility_type         VARCHAR(10),
    facility_subtype_desc VARCHAR(120),
    facility_name         VARCHAR(200),
    facility_location     VARCHAR(40),
    activity_id           VARCHAR(20) NOT NULL,
    product_id            VARCHAR(20) NOT NULL,
    from_to_id            VARCHAR(30) NOT NULL DEFAULT '',
    volume                NUMERIC(18, 4),
    energy                NUMERIC(18, 4),
    hours                 NUMERIC(10, 2),
    -- Petrinex masks confidential volumes with '***'; the row is kept and
    -- flagged rather than dropped or silently coerced to NULL.
    volume_masked         BOOLEAN NOT NULL DEFAULT FALSE,
    province              VARCHAR(10) DEFAULT 'AB',
    loaded_at             TIMESTAMP DEFAULT NOW()
);

-- Natural key verified unique across a full month of unmasked records.
-- from_to_id defaults to '' because NULLs never compare equal in a unique index.
CREATE UNIQUE INDEX IF NOT EXISTS uq_facility_production_record
    ON facility_production(production_month, facility_id, activity_id, product_id, from_to_id);

CREATE INDEX IF NOT EXISTS idx_facility_month ON facility_production(production_month);
CREATE INDEX IF NOT EXISTS idx_facility_operator ON facility_production(operator_name);
CREATE INDEX IF NOT EXISTS idx_facility_product ON facility_production(product_id);
CREATE INDEX IF NOT EXISTS idx_facility_activity_product
    ON facility_production(activity_id, product_id);
