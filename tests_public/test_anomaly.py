from student_api import detect_metric


def test_large_volume_drop_is_anomaly():
    history = [1000, 1010, 995, 1008, 1004, 1012, 998]
    result = detect_metric(300, history, method="zscore")
    assert result["is_anomaly"] is True


def test_stable_value_is_not_anomaly():
    history = [1000, 1010, 995, 1008, 1004, 1012, 998]
    result = detect_metric(1002, history, method="zscore")
    assert result["is_anomaly"] is False


def test_mad_detector_robust_to_zero_mad():
    history = [100, 100, 100, 100, 100]
    result_same = detect_metric(100, history, method="mad")
    assert result_same["is_anomaly"] is False
    result_diff = detect_metric(200, history, method="mad")
    assert result_diff["is_anomaly"] is True


def test_auto_context_seasonality():
    overall_history = [1000, 1020, 1010, 1005, 500, 520, 510]  # Weekdays vs Weekends
    weekend_history = [500, 520, 510, 505, 515]
    result = detect_metric(
        508,
        overall_history,
        method="auto",
        context={"day_of_week": 6, "same_segment_history": weekend_history},
    )
    assert result["is_anomaly"] is False


def test_auto_known_event_suppresses_explained_anomaly():
    result = detect_metric(
        200,
        [100, 100, 100, 100, 100],
        method="auto",
        context={"known_event": "planned_campaign"},
    )

    assert result["is_anomaly"] is False
    assert "known_event" in result["reason"]
