from student_api import column_downstream, downstream_assets


def test_transitive_downstream_assets():
    graph = {
        "raw_orders": ["stg_orders"],
        "stg_orders": ["revenue"],
        "revenue": ["dashboard"],
    }
    assert downstream_assets(graph, "raw_orders") == ["stg_orders", "revenue", "dashboard"]


def test_transitive_column_downstream():
    col_graph = {
        "raw_orders.order_amount": ["stg_orders.amount_usd"],
        "stg_orders.amount_usd": ["fct_daily_revenue.daily_revenue"],
        "fct_daily_revenue.daily_revenue": ["dashboard.total_revenue_kpi"],
    }
    assert column_downstream(col_graph, "raw_orders.order_amount") == [
        "stg_orders.amount_usd",
        "fct_daily_revenue.daily_revenue",
        "dashboard.total_revenue_kpi",
    ]
