-- The upsert in scripts/load.py keys on (field_name, operator,
-- production_date) per source table, so the combined fact table must be
-- unique on the same key plus energy_source. Any rows returned fail the test.
select
    energy_source,
    field_name,
    operator,
    production_date,
    count(*) as duplicate_count
from {{ ref('fct_production') }}
group by energy_source, field_name, operator, production_date
having count(*) > 1
