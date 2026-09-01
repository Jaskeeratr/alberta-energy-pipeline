-- The bulk upsert in scripts/load.py merges on this key, so a duplicate here
-- would mean the unique index was bypassed. Any rows returned fail the test.
select
    production_month,
    facility_id,
    activity_id,
    product_id,
    from_to_id,
    count(*) as duplicate_count
from {{ ref('stg_facility_production') }}
group by production_month, facility_id, activity_id, product_id, from_to_id
having count(*) > 1
