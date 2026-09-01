-- Reported production volumes per month and product, from Petrinex facility
-- data. Masked volumes are excluded from the totals but counted separately so
-- the suppression is visible rather than silently folded into the numbers.
select
    production_month,
    production_year,
    product_id,
    count(*) as record_count,
    count(distinct facility_id) as facility_count,
    count(distinct operator_name) as operator_count,
    sum(volume) filter (where not volume_masked) as total_volume,
    count(*) filter (where volume_masked) as masked_record_count
from {{ ref('stg_facility_production') }}
where activity_id = 'PROD'
group by production_month, production_year, product_id
order by production_month, product_id
