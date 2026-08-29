-- Singular test: Fails if any customer has multiple active records (causes fanout in fct_daily_revenue)
select
    customer_id,
    count(*) as active_count
from {{ ref('stg_customers') }}
where is_active = true
group by customer_id
having count(*) > 1
