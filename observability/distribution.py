"""Distribution shift detection using Kolmogorov-Smirnov statistic, mean ratio, and quantile comparison."""
from __future__ import annotations

from typing import Any, Iterable

import numpy as np


def _two_sample_ks(data1: np.ndarray, data2: np.ndarray) -> tuple[float, float]:
    """Compute 2-sample Kolmogorov-Smirnov statistic without relying on heavy external dependencies."""
    n1 = len(data1)
    n2 = len(data2)
    if n1 == 0 or n2 == 0:
        return 0.0, 1.0
    data1_sorted = np.sort(data1)
    data2_sorted = np.sort(data2)
    data_all = np.concatenate([data1_sorted, data2_sorted])
    cdf1 = np.searchsorted(data1_sorted, data_all, side="right") / n1
    cdf2 = np.searchsorted(data2_sorted, data_all, side="right") / n2
    d_stat = float(np.max(np.abs(cdf1 - cdf2)))
    # Approximate asymptotic p-value
    en = np.sqrt(n1 * n2 / (n1 + n2))
    p_val = float(np.clip(2.0 * np.exp(-2.0 * (en * d_stat) ** 2), 0.0, 1.0))
    return d_stat, p_val


def detect_distribution_shift(
    current_values: Iterable[float],
    baseline_values: Iterable[float],
    *,
    ratio_threshold: float = 3.0,
    ks_threshold: float = 0.35,
) -> dict[str, Any]:
    """Detect distribution drift between baseline and current observation batches.
    
    Combines Kolmogorov-Smirnov statistic and mean ratio to detect both shape/variance
    shifts and severe scale changes.
    """
    cur = np.asarray(list(current_values), dtype=float)
    base = np.asarray(list(baseline_values), dtype=float)
    if cur.size == 0 or base.size == 0:
        return {"is_anomaly": False, "score": 0.0, "method": "distribution_shift", "reason": "empty_input"}

    cur_mean = float(np.mean(cur))
    base_mean = float(np.mean(base))

    # 1. Mean ratio
    if base_mean == 0:
        mean_ratio = float("inf") if cur_mean != 0 else 1.0
    else:
        mean_ratio = max(abs(cur_mean / base_mean), abs(base_mean / cur_mean)) if cur_mean != 0 else float("inf")

    # 2. Two-sample KS statistic
    ks_stat, p_val = _two_sample_ks(cur, base)

    # Anomaly if extreme mean shift OR significant distribution CDF divergence
    is_mean_anomaly = bool(mean_ratio >= ratio_threshold)
    is_ks_anomaly = bool(ks_stat >= ks_threshold and p_val < 0.05)
    is_anomaly = is_mean_anomaly or is_ks_anomaly

    score = max(float(mean_ratio if mean_ratio != float("inf") else 999.0), float(ks_stat * 10.0))

    return {
        "is_anomaly": is_anomaly,
        "score": float(score),
        "method": "ks_and_mean_ratio",
        "ks_stat": float(ks_stat),
        "mean_ratio": float(mean_ratio),
        "reason": f"baseline_mean={base_mean:.3f}, current_mean={cur_mean:.3f}, ks_stat={ks_stat:.3f}, p_val={p_val:.4f}",
    }
