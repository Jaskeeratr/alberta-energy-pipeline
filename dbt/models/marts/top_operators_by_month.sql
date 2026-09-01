-- Operator league table per production month, ranked by reported volume.
with operator_totals as (
    select
        production_month,
        operator_name,
        product_id,
        count(distinct facility_id) as facility_count,
        sum(volume) filter (where not volume_masked) as total_volume
    from {{ ref('stg_facility_production') }}
    where activity_id = 'PROD'
    group by production_month, operator_name, product_id
)
select
    production_month,
    operator_name,
    product_id,
    facility_count,
    total_volume,
    rank() over (
        partition by production_month, product_id
        order by total_volume desc nulls last
    ) as volume_rank
from operator_totals
