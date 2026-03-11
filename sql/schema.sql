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
