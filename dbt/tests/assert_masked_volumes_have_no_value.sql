-- A masked row must never carry a numeric volume: that would mean a
-- confidential value leaked into the totals. Any rows returned fail the test.
select *
from {{ ref('stg_facility_production') }}
where volume_masked and volume is not null
