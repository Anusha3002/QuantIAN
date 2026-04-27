from __future__ import annotations

from azure_anomaly.service import AnomalyService
from shared.schemas import MarketEvent


def _event(symbol: str, price_change: float, volume_change: float, event_id: str = "evt") -> MarketEvent:
    return MarketEvent(
        event_id=event_id,
        symbol=symbol,
        asset_class="crypto",
        price=100.0,
        volume=1000.0,
        source="test",
        window={"price_change_1m": price_change, "volume_change_1m": volume_change},
    )


def test_rule_score_flat_series_produces_low_score() -> None:
    features = [0.001, 0.01, 100.0, 1000.0]
    history = [[0.001, 0.01, 100.0, 1000.0]] * 10
    score = AnomalyService._rule_based_score(features, history)
    assert score < 0.8


def test_rule_score_big_spike_triggers_high_score(tmp_path) -> None:
    service = AnomalyService(node_id="test-anom", state_path=tmp_path / "state.json")
    # prime with 20 quiet samples
    for i in range(20):
        service.analyze_event(_event("BTC", 0.001, 0.005, event_id=f"evt-{i}"))

    # now a large spike
    alert = service.analyze_event(_event("BTC", 0.12, 0.5, event_id="evt-spike"))
    assert alert is not None
    assert alert.severity in ("high", "critical", "medium")
    assert alert.status == "pending_review"


def test_threshold_prevents_alerts_for_minor_noise(tmp_path) -> None:
    service = AnomalyService(
        node_id="test-anom",
        state_path=tmp_path / "state.json",
        alert_threshold=0.82,
    )
    # feed only minor deltas — should not produce alerts
    alert_count = 0
    for i in range(30):
        alert = service.analyze_event(_event("ETH", 0.001, 0.002, event_id=f"evt-{i}"))
        if alert is not None:
            alert_count += 1
    assert alert_count == 0


def test_review_updates_alert_status(tmp_path) -> None:
    from shared.schemas import AnomalyAlertReview

    service = AnomalyService(node_id="test-anom", state_path=tmp_path / "state.json")
    for i in range(15):
        service.analyze_event(_event("BTC", 0.001, 0.005, event_id=f"p-{i}"))
    alert = service.analyze_event(_event("BTC", 0.1, 0.5, event_id="x"))
    assert alert is not None

    review = AnomalyAlertReview(reviewer="tester", status="confirmed", notes="real spike")
    updated = service.review_alert(alert.alert_id, review)
    assert updated.status == "confirmed"


def test_severity_brackets_are_monotonic() -> None:
    assert AnomalyService._severity(0.99) == "critical"
    assert AnomalyService._severity(0.92) == "high"
    assert AnomalyService._severity(0.86) == "medium"
    assert AnomalyService._severity(0.5) == "low"
