"""Contract validator supporting deterministic checks, type verification, and freshness.

Supports both column-based and field-based contracts with severity levels (critical, warning, info).
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml


def _issue(
    check: str,
    *,
    column: str | None,
    severity: str,
    passed: bool,
    details: str,
) -> dict[str, Any]:
    return {
        "check": check,
        "column": column,
        "severity": severity,
        "passed": bool(passed),
        "details": details,
    }


def load_contract(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _validate_type(series: pd.Series, expected_type: str) -> tuple[bool, str]:
    non_null = series.dropna()
    if non_null.empty:
        return True, "empty_series"

    type_norm = str(expected_type).lower().strip()
    if type_norm in {"integer", "int"}:
        try:
            numeric = pd.to_numeric(non_null, errors="coerce")
            if numeric.isna().any():
                invalid_count = int(numeric.isna().sum())
                return False, f"invalid_integer_format_count={invalid_count}"
            # Check if all numbers are integers (no fractional part)
            is_int = np.isclose(numeric, np.round(numeric))
            if not is_int.all():
                invalid_count = int((~is_int).sum())
                return False, f"non_integer_values_count={invalid_count}"
            return True, "valid_integer"
        except Exception as e:
            return False, f"type_error: {e}"

    elif type_norm in {"number", "float", "numeric", "double"}:
        numeric = pd.to_numeric(non_null, errors="coerce")
        if numeric.isna().any():
            invalid_count = int(numeric.isna().sum())
            return False, f"invalid_numeric_count={invalid_count}"
        return True, "valid_number"

    elif type_norm in {"string", "str", "text"}:
        is_str = non_null.apply(lambda x: isinstance(x, str))
        if not is_str.all():
            invalid_count = int((~is_str).sum())
            return False, f"non_string_count={invalid_count}"
        return True, "valid_string"

    elif type_norm in {"datetime", "timestamp"}:
        parsed = pd.to_datetime(non_null, utc=True, errors="coerce")
        if parsed.isna().any():
            invalid_count = int(parsed.isna().sum())
            return False, f"invalid_datetime_count={invalid_count}"
        return True, "valid_datetime"

    elif type_norm in {"boolean", "bool"}:
        is_bool = non_null.apply(lambda x: isinstance(x, (bool, np.bool_)) or str(x).lower() in {"true", "false", "1", "0"})
        if not is_bool.all():
            invalid_count = int((~is_bool).sum())
            return False, f"non_boolean_count={invalid_count}"
        return True, "valid_boolean"

    return True, f"unknown_type_{expected_type}"


def validate_dataframe(df: pd.DataFrame, contract: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    columns = contract.get("columns") or contract.get("fields") or {}

    for column, rules in columns.items():
        if not isinstance(rules, dict):
            rules = {}
        severity = rules.get("severity", "warning")
        required = bool(rules.get("required", False))

        if column not in df.columns:
            if required:
                issues.append(
                    _issue(
                        "required_column",
                        column=column,
                        severity=severity,
                        passed=False,
                        details=f"Missing required column: {column}",
                    )
                )
            continue

        series = df[column]

        # 1. Not-null check
        if required:
            null_count = int(series.isna().sum())
            issues.append(
                _issue(
                    "not_null",
                    column=column,
                    severity=severity,
                    passed=(null_count == 0),
                    details=f"null_count={null_count}",
                )
            )

        # 2. Type validation
        if "type" in rules:
            passed_type, type_details = _validate_type(series, rules["type"])
            issues.append(
                _issue(
                    "type",
                    column=column,
                    severity=severity,
                    passed=passed_type,
                    details=f"declared_type={rules['type']}; {type_details}",
                )
            )

        # 3. Unique check
        if rules.get("unique"):
            duplicate_count = int(series.duplicated(keep=False).sum())
            issues.append(
                _issue(
                    "unique",
                    column=column,
                    severity=severity,
                    passed=(duplicate_count == 0),
                    details=f"duplicate_rows={duplicate_count}",
                )
            )

        # 4. Accepted values check
        accepted = rules.get("accepted_values")
        if accepted is not None:
            invalid_mask = series.notna() & ~series.isin(accepted)
            invalid_count = int(invalid_mask.sum())
            issues.append(
                _issue(
                    "accepted_values",
                    column=column,
                    severity=severity,
                    passed=(invalid_count == 0),
                    details=f"invalid_count={invalid_count}; accepted={accepted}",
                )
            )

        # 5. Numeric range check
        if "min" in rules or "max" in rules:
            numeric = pd.to_numeric(series, errors="coerce")
            invalid = pd.Series(False, index=series.index)
            if "min" in rules:
                invalid |= numeric < rules["min"]
            if "max" in rules:
                invalid |= numeric > rules["max"]
            invalid_count = int(invalid.fillna(False).sum())
            issues.append(
                _issue(
                    "range",
                    column=column,
                    severity=severity,
                    passed=(invalid_count == 0),
                    details=f"invalid_count={invalid_count}",
                )
            )

        # 6. Min length check for strings
        if "min_length" in rules:
            min_len = int(rules["min_length"])
            str_series = series.dropna().astype(str)
            too_short = int((str_series.str.len() < min_len).sum())
            issues.append(
                _issue(
                    "min_length",
                    column=column,
                    severity=severity,
                    passed=(too_short == 0),
                    details=f"too_short_count={too_short}; min_length={min_len}",
                )
            )

    # 7. Freshness check at contract level
    freshness_cfg = contract.get("freshness")
    if freshness_cfg and isinstance(freshness_cfg, dict):
        fresh_col = freshness_cfg.get("column")
        max_delay = float(freshness_cfg.get("max_delay_minutes", 60.0))
        fresh_severity = freshness_cfg.get("severity", "warning")

        if fresh_col and fresh_col in df.columns and not df[fresh_col].empty:
            parsed_dates = pd.to_datetime(df[fresh_col], utc=True, errors="coerce")
            valid_dates = parsed_dates.dropna()
            if not valid_dates.empty:
                max_ts = valid_dates.max()
                now_utc = pd.Timestamp(datetime.now(timezone.utc))
                delay_minutes = max(0.0, (now_utc - max_ts).total_seconds() / 60.0)
                is_fresh = delay_minutes <= max_delay
                issues.append(
                    _issue(
                        "freshness",
                        column=fresh_col,
                        severity=fresh_severity,
                        passed=is_fresh,
                        details=f"delay_minutes={delay_minutes:.1f}; max_delay_minutes={max_delay}",
                    )
                )
            else:
                issues.append(
                    _issue(
                        "freshness",
                        column=fresh_col,
                        severity=fresh_severity,
                        passed=False,
                        details="freshness_column_has_no_valid_timestamps",
                    )
                )

    return issues


def failed_issues(issues: list[dict[str, Any]], min_severity: str | None = None) -> list[dict[str, Any]]:
    failed = [i for i in issues if not i.get("passed", False)]
    if min_severity is None:
        return failed
    order = {"info": 0, "warning": 1, "critical": 2}
    threshold = order.get(min_severity, 1)
    return [i for i in failed if order.get(i.get("severity", "warning"), 1) >= threshold]


def determine_action(issues: list[dict[str, Any]]) -> str:
    """Determine pipeline action based on issues severity."""
    failed = [i for i in issues if not i.get("passed", False)]
    if not failed:
        return "pass"
    severities = {i.get("severity", "warning") for i in failed}
    if "critical" in severities:
        return "block"
    if "warning" in severities:
        return "quarantine"
    return "warn"
