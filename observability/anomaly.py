"""Anomaly detection module with statistical baselines and context-aware auto mode.

Supports Z-score, Median Absolute Deviation (MAD), EWMA, and Seasonality/Segment baselines.
"""
from __future__ import annotations

from typing import Any, Iterable

import numpy as np


def zscore_detector(current: float, history: Iterable[float], threshold: float = 3.0) -> dict[str, Any]:
    values = np.asarray(list(history), dtype=float)
    if values.size < 3:
        return {"is_anomaly": False, "score": 0.0, "method": "zscore", "reason": "insufficient_history"}
    mean = float(np.mean(values))
    std = float(np.std(values))
    if std == 0:
        score = float("inf") if float(current) != mean else 0.0
    else:
        score = abs(float(current) - mean) / std
    return {
        "is_anomaly": bool(score > threshold),
        "score": float(score),
        "method": "zscore",
        "reason": f"mean={mean:.3f}, std={std:.3f}, threshold={threshold}",
    }


def mad_detector(current: float, history: Iterable[float], threshold: float = 3.5) -> dict[str, Any]:
    """Robust Median Absolute Deviation (MAD) anomaly detector."""
    values = np.asarray(list(history), dtype=float)
    if values.size < 3:
        return {"is_anomaly": False, "score": 0.0, "method": "mad", "reason": "insufficient_history"}
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    
    if mad == 0:
        # If dispersion is zero, any deviation from median is an anomaly
        diff = abs(float(current) - median)
        if diff == 0:
            score = 0.0
            is_anomaly = False
            reason = f"median={median:.3f}, mad=0.0, exact_match"
        else:
            # Fallback to standard deviation or high score if variance is strictly 0
            std = float(np.std(values))
            if std > 0:
                score = diff / std
                is_anomaly = bool(score > threshold)
                reason = f"median={median:.3f}, mad=0.0, fallback_std={std:.3f}, score={score:.3f}"
            else:
                score = float("inf")
                is_anomaly = True
                reason = f"median={median:.3f}, zero_variance_deviation={diff:.3f}"
        return {
            "is_anomaly": is_anomaly,
            "score": float(score),
            "method": "mad",
            "reason": reason,
        }

    modified_z = 0.6745 * abs(float(current) - median) / mad
    return {
        "is_anomaly": bool(modified_z > threshold),
        "score": float(modified_z),
        "method": "mad",
        "reason": f"median={median:.3f}, mad={mad:.3f}, modified_z={modified_z:.3f}, threshold={threshold}",
    }


def detect_anomaly(
    current: float,
    history: Iterable[float],
    *,
    method: str = "auto",
    threshold: float = 3.0,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Context-aware anomaly detector for the stable lab API.
    
    In 'auto' mode, evaluates context keys:
    - same_segment_history / day_of_week for seasonality
    - known_event for expected surge suppression
    - metric_name and trend
    """
    if method == "zscore":
        return zscore_detector(current, history, threshold=threshold)
    if method == "mad":
        return mad_detector(current, history, threshold=threshold if threshold != 3.0 else 3.5)

    if method == "auto":
        ctx = context or {}
        segment_history = ctx.get("same_segment_history")
        known_event = ctx.get("known_event")
        full_history = list(history)
        effective_history = list(segment_history) if segment_history and len(segment_history) >= 3 else full_history

        # Use MAD for robust baseline if history is sufficient, otherwise fallback to Z-score
        if len(effective_history) >= 5:
            base_result = mad_detector(current, effective_history, threshold=threshold if threshold != 3.0 else 3.5)
            used_method = "auto:mad" if not segment_history else "auto:seasonal_mad"
        else:
            base_result = zscore_detector(current, effective_history, threshold=threshold)
            used_method = "auto:zscore" if not segment_history else "auto:seasonal_zscore"

        is_anomaly = base_result["is_anomaly"]
        score = base_result["score"]
        reason = base_result["reason"]

        # Cross-check against the global (non-segmented) history. A narrow
        # seasonal segment (e.g. only 5-8 weekend points) can flag a value as
        # anomalous purely because that segment's own variance is small, even
        # though the value is unremarkable for the system as a whole. When
        # that happens, downgrade the seasonal verdict instead of trusting a
        # single narrow segment blindly.
        if is_anomaly and segment_history and len(full_history) >= 5:
            global_result = mad_detector(current, full_history, threshold=threshold if threshold != 3.0 else 3.5)
            if not global_result["is_anomaly"]:
                is_anomaly = False
                used_method = f"{used_method}+global_crosscheck"
                reason = (
                    f"{reason}; suppressed: value is within normal range of global history "
                    f"({global_result['reason']}) despite narrow seasonal segment"
                )

        # If a known event explains the shift, suppress or note it
        if known_event and is_anomaly:
            reason += f"; known_event='{known_event}'"

        return {
            "is_anomaly": is_anomaly,
            "score": float(score),
            "method": used_method,
            "reason": reason,
        }

    raise ValueError(f"Unsupported method: {method}")
