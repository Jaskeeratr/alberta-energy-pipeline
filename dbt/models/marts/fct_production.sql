select
    'crude_oil' as energy_source,
    field_name,
    operator,
    production_date,
    production_year,
    volume_m3,
    province,
    loaded_at
from {{ ref('stg_oil_production') }}

union all

select
    'natural_gas' as energy_source,
    field_name,
    operator,
    production_date,
    production_year,
    volume_m3,
    province,
    loaded_at
from {{ ref('stg_gas_production') }}
