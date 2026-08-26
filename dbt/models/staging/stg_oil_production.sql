select
    field_name,
    operator,
    production_date,
    extract(year from production_date)::int as production_year,
    volume_m3,
    province,
    loaded_at
from {{ source('raw', 'oil_production') }}
