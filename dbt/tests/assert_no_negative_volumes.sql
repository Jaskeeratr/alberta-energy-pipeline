-- Production volumes can be zero but never negative. Any rows returned
-- fail the test.
select *
from {{ ref('fct_production') }}
where volume_m3 < 0
