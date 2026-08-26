select
    energy_source,
    production_year,
    count(*) as record_count,
    sum(volume_m3) as total_volume_m3,
    avg(volume_m3) as avg_volume_m3,
    max(volume_m3) as max_volume_m3
from {{ ref('fct_production') }}
group by energy_source, production_year
order by energy_source, production_year
