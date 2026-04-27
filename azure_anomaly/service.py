from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path
from statistics import mean, pstdev

from shared.schemas import AnomalyAlert, AnomalyAlertReview, MarketEvent
from shared.storage import FileJsonStateStore, JsonStateStore
from shared.utils.ids import make_prefixed_id
from shared.utils.ledger import LedgerAppender, record_ledger_event

try:
    from sklearn.ensemble import IsolationForest
except ImportError:  # pragma: no cover - optional dependency
    IsolationForest = None


class AnomalyService:
    def __init__(
        self,
        node_id: str,
        ledger_appender: LedgerAppender | None = None,
        *,
        alert_threshold: float = 0.82,
        history_window: int = 60,
        state_path: str | Path | None = None,
        state_store: JsonStateStore | None = None,
    ) -> None:
        self.node_id = node_id
        self.ledger_appender = ledger_appender
        self.alert_threshold = alert_threshold
        self.history_window = history_window
        self.state_path = Path(state_path) if state_path is not None else None
        self.state_store = state_store or FileJsonStateStore(self.state_path)
        self.history_by_symbol: dict[str, deque[list[float]]] = defaultdict(lambda: deque(maxlen=history_window))
        self.alerts: dict[str, AnomalyAlert] = {}
        self._load_state()

    def analyze_event(self, event: MarketEvent) -> AnomalyAlert | None:
        features = self._extract_features(event)
        history = list(self.history_by_symbol[event.symbol])

        rule_score = self._rule_based_score(features, history)
        model_score = self._model_score(features, history)
        score = max(rule_score, model_score)

        self.history_by_symbol[event.symbol].append(features)

        if score < self.alert_threshold:
            return None

        alert = AnomalyAlert(
            alert_id=make_prefixed_id("alt"),
            event_id=event.event_id,
            symbol=event.symbol,
            severity=self._severity(score),
            score=round(score, 4),
            reason=self._reason(features, rule_score, model_score),
            status="pending_review",
        )
        self.alerts[alert.alert_id] = alert
        self._save_state()

        record_ledger_event(
            self.ledger_appender,
            event_type="anomaly_alert_created",
            actor_node=self.node_id,
            payload=alert.model_dump(),
        )
        return alert

    def review_alert(self, alert_id: str, review: AnomalyAlertReview) -> AnomalyAlert:
        alert = self.alerts[alert_id]
        updated = alert.model_copy(update={"status": review.status})
        self.alerts[alert_id] = updated
        self._save_state()
        record_ledger_event(
            self.ledger_appender,
            event_type="anomaly_alert_reviewed",
            actor_node=self.node_id,
            payload={
                "alert_id": alert_id,
                "review": review.model_dump(),
            },
        )
        return updated

    def list_alerts(self) -> list[AnomalyAlert]:
        return list(self.alerts.values())

    def get_alert(self, alert_id: str) -> AnomalyAlert | None:
        return self.alerts.get(alert_id)

    def health(self) -> dict[str, object]:
        return {
            "status": "ok",
            "service": "azure_anomaly",
            "node_id": self.node_id,
            "alerts": len(self.alerts),
            "tracked_symbols": len(self.history_by_symbol),
            "sklearn_enabled": IsolationForest is not None,
            "storage_backend": self.state_store.__class__.__name__,
        }

    @staticmethod
    def _extract_features(event: MarketEvent) -> list[float]:
        price_change = float(event.window.get("price_change_1m", 0.0))
        volume_change = float(event.window.get("volume_change_1m", 0.0))
        return [price_change, volume_change, float(event.price), float(event.volume)]

    @staticmethod
    def _rule_based_score(features: list[float], history: list[list[float]]) -> float:
        price_change = abs(features[0])
        volume_change = abs(features[1])

        if not history:
            return min(1.0, price_change * 8.0 + volume_change * 3.0)

        price_history = [abs(item[0]) for item in history]
        volume_history = [abs(item[1]) for item in history]

        price_baseline = mean(price_history) + (2 * pstdev(price_history) if len(price_history) > 1 else 0.0)
        volume_baseline = mean(volume_history) + (2 * pstdev(volume_history) if len(volume_history) > 1 else 0.0)

        price_score = price_change / max(price_baseline, 0.01)
        volume_score = volume_change / max(volume_baseline, 0.02)
        return min(1.0, 0.65 * price_score + 0.35 * volume_score)

    @staticmethod
    def _model_score(features: list[float], history: list[list[float]]) -> float:
        if IsolationForest is None or len(history) < 12:
            return 0.0

        model = IsolationForest(contamination=0.1, random_state=42)
        model.fit(history)
        raw_score = float(-model.score_samples([features])[0])
        return min(1.0, max(0.0, (raw_score - 0.35) / 0.35))

    @staticmethod
    def _severity(score: float) -> str:
        if score >= 0.95:
            return "critical"
        if score >= 0.9:
            return "high"
        if score >= 0.85:
            return "medium"
        return "low"

    @staticmethod
    def _reason(features: list[float], rule_score: float, model_score: float) -> str:
        parts = []
        if abs(features[0]) >= 0.03:
            parts.append("price spike")
        if abs(features[1]) >= 0.2:
            parts.append("volume surge")
        if model_score >= 0.8:
            parts.append("isolation forest outlier")
        if not parts:
            parts.append("combined deviation threshold exceeded")
        parts.append(f"rule={rule_score:.2f}")
        if model_score > 0:
            parts.append(f"model={model_score:.2f}")
        return ", ".join(parts)

    def _load_state(self) -> None:
        payload = self.state_store.load_json({"alerts": {}, "history_by_symbol": {}})
        self.alerts = {
            alert_id: AnomalyAlert.model_validate(item)
            for alert_id, item in payload.get("alerts", {}).items()
        }
        self.history_by_symbol = defaultdict(lambda: deque(maxlen=self.history_window))
        for symbol, items in payload.get("history_by_symbol", {}).items():
            self.history_by_symbol[symbol] = deque(items, maxlen=self.history_window)

    def _save_state(self) -> None:
        self.state_store.save_json(
            {
                "alerts": {alert_id: alert.model_dump() for alert_id, alert in self.alerts.items()},
                "history_by_symbol": {symbol: list(items) for symbol, items in self.history_by_symbol.items()},
            }
        )
