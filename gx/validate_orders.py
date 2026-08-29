#!/usr/bin/env python3
"""Great Expectations Core 1.21 modern validation flow with Expectation Suite, Validation Definition, and Checkpoint."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import great_expectations as gx
except ImportError as exc:
    raise SystemExit("great_expectations is not installed. Run: pip install -r requirements.txt") from exc


def build_orders_suite() -> gx.ExpectationSuite:
    suite = gx.ExpectationSuite(name="orders_expectation_suite")
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="order_id")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeUnique(column="order_id")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeBetween(column="amount", min_value=0)
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeInSet(column="currency", value_set=["USD", "VND"])
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeInSet(
            column="status", value_set=["pending", "completed", "refunded", "cancelled"]
        )
    )
    return suite


def main() -> None:
    orders_path = ROOT / "data" / "incoming" / "orders.csv"
    if not orders_path.exists():
        print(f"Orders file not found at {orders_path}")
        return

    df = pd.read_csv(orders_path)
    context = gx.get_context(mode="ephemeral")

    data_source = context.data_sources.add_pandas("orders_datasource")
    asset = data_source.add_dataframe_asset(name="orders_asset")
    batch_definition = asset.add_batch_definition_whole_dataframe("whole_dataframe_batch")
    
    suite = build_orders_suite()
    suite = context.suites.add(suite)
    
    val_def = gx.ValidationDefinition(
        name="orders_validation_definition",
        data=batch_definition,
        suite=suite,
    )
    val_def = context.validation_definitions.add(val_def)

    checkpoint = gx.Checkpoint(
        name="orders_checkpoint",
        validation_definitions=[val_def],
    )
    checkpoint = context.checkpoints.add(checkpoint)

    batch_params = {"dataframe": df}
    checkpoint_result = checkpoint.run(batch_parameters=batch_params)
    
    success = checkpoint_result.success
    print("=== Great Expectations 1.21 Checkpoint Result ===")
    print(f"Suite: {suite.name}")
    print(f"Status: {'PASS' if success else 'FAIL'}")
    for res in checkpoint_result.run_results.values():
        for r in res.results:
            exp_type = getattr(r.expectation_config, "type", None) or getattr(r.expectation_config, "expectation_type", "expectation")
            col = r.expectation_config.kwargs.get("column", "") if hasattr(r, "expectation_config") else ""
            print(f" - {exp_type:<38} column={col:<15} success={r.success}")

    if not success:
        print("\n[ALERT] Data quality checkpoint failed. Action: BLOCK pipeline ingestion.")
    else:
        print("\n[OK] All Great Expectations validation checks passed.")


if __name__ == "__main__":
    main()
