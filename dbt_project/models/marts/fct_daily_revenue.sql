-- The customer dimension (SCD) can carry more than one active row per
-- customer_id. A plain left join on that raw dimension fans out completed
-- orders and inflates both completed_order_rows and daily_revenue without
-- any SQL error. We deduplicate to exactly one active row per customer_id
-- before joining so revenue reflects reality regardless of upstream SCD
-- duplicates. See unit test `scd_duplicate_customer_inflates_revenue`.

with completed_orders as (
    select *
    from {{ ref('stg_orders') }}
    where status = 'completed'
),
active_customers as (
    select customer_id, is_active
    from (
        select
            customer_id,
            is_active,
            row_number() over (
                partition by customer_id
                order by customer_id
            ) as rn
        from {{ ref('stg_customers') }}
        where is_active = true
    )
    where rn = 1
)
select
    o.order_date,
    count(*) as completed_order_rows,
    sum(o.amount_usd) as daily_revenue
from completed_orders o
left join active_customers c
    on o.customer_id = c.customer_id
group by 1
order by 1
