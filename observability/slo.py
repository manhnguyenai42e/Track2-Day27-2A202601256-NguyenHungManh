"""SLI/SLO and Multi-Window Multi-Burn-Rate Alerting based on Google SRE principles."""
from __future__ import annotations

from typing import Any


def calculate_slo(target: float, bad_events: int, total_events: int) -> dict[str, Any]:
    if not 0 < target < 1:
        raise ValueError("target must be between 0 and 1 (exclusive)")
    if bad_events < 0 or total_events < 0 or bad_events > total_events:
        raise ValueError("invalid event counts")
    allowed_bad_rate = 1.0 - target
    if total_events == 0:
        return {
            "target": target,
            "actual_bad_rate": 0.0,
            "allowed_bad_rate": allowed_bad_rate,
            "burn_rate": 0.0,
            "remaining_error_budget_fraction": 1.0,
            "breached": False,
        }
    actual_bad_rate = bad_events / total_events
    burn_rate = actual_bad_rate / allowed_bad_rate
    consumed_fraction = min(1.0, actual_bad_rate / allowed_bad_rate)
    return {
        "target": target,
        "actual_bad_rate": actual_bad_rate,
        "allowed_bad_rate": allowed_bad_rate,
        "burn_rate": burn_rate,
        "remaining_error_budget_fraction": max(0.0, 1.0 - consumed_fraction),
        "breached": bool(actual_bad_rate > allowed_bad_rate),
    }


def evaluate_multiwindow_burn(
    *,
    short_window_burn: float,
    long_window_burn: float,
    policy: str = "google_sre",
) -> dict[str, Any]:
    """Evaluate multi-window multi-burn-rate alerting.
    
    Prevents alert fatigue by requiring both short and long windows to exceed
    thresholds before paging on-call.
    - Critical (Page): short >= 14.4x (2% budget in 1h) and long >= 14.4x
    - Warning (Page/Ticket): short >= 6.0x (5% budget in 6h) and long >= 6.0x
    - Transient Spike: short is high but long is low -> No page (info/ticket)
    """
    short = float(short_window_burn)
    long = float(long_window_burn)

    # 1. Sustained Critical Fast Burn (14.4x)
    if short >= 14.4 and long >= 14.4:
        return {
            "page": True,
            "severity": "critical",
            "reason": f"Sustained 14.4x burn rate across 1h/6h windows (short={short:.1f}, long={long:.1f})",
            "short_window_burn": short,
            "long_window_burn": long,
        }

    # 2. Sustained Fast Burn (6.0x)
    if short >= 6.0 and long >= 6.0:
        return {
            "page": True,
            "severity": "warning",
            "reason": f"Sustained 6.0x burn rate across 1h/6h windows (short={short:.1f}, long={long:.1f})",
            "short_window_burn": short,
            "long_window_burn": long,
        }

    # 3. Transient Spike (short window burned fast, but long window is healthy)
    if short >= 6.0 and long < 6.0:
        return {
            "page": False,
            "severity": "info",
            "reason": f"Transient spike detected (short={short:.1f}), suppressed because long window is healthy (long={long:.1f})",
            "short_window_burn": short,
            "long_window_burn": long,
        }

    # 4. Normal / within budget
    return {
        "page": False,
        "severity": "info",
        "reason": f"Burn rate within normal operating parameters (short={short:.1f}, long={long:.1f})",
        "short_window_burn": short,
        "long_window_burn": long,
    }
