from __future__ import annotations

import math
from collections import defaultdict
from pathlib import Path
from statistics import pstdev

from shared.schemas import MarketEvent, Portfolio, RiskSnapshot
from shared.storage import load_json_file, save_json_file
from shared.utils.ids import make_prefixed_id
from shared.utils.ledger import LedgerAppender, record_ledger_event


class RiskService:
    def __init__(
        self,
        node_id: str,
        ledger_appender: LedgerAppender | None = None,
        *,
        state_path: str | Path | None = None,
        auto_compute: bool = False,
    ) -> None:
        self.node_id = node_id
        self.ledger_appender = ledger_appender
        self.state_path = Path(state_path) if state_path is not None else None
        self.auto_compute = auto_compute
        self.events_by_symbol: dict[str, list[MarketEvent]] = defaultdict(list)
        self.portfolio: Portfolio | None = None
        self.snapshots: list[RiskSnapshot] = []
        self._load_state()

    def set_portfolio(self, portfolio: Portfolio) -> Portfolio:
        self.portfolio = portfolio
        self._save_state()
        return portfolio

    def ingest_event(self, event: MarketEvent) -> MarketEvent:
        self.events_by_symbol[event.symbol].append(event)
        self._save_state()
        if self.auto_compute and self.portfolio is not None:
            self.compute_risk()
        return event

    def compute_risk(self, portfolio: Portfolio | None = None) -> RiskSnapshot:
        effective_portfolio = portfolio or self.portfolio
        if effective_portfolio is None:
            raise ValueError("portfolio is required before risk can be computed")

        series_by_symbol = {
            position.symbol: self._returns_for_symbol(position.symbol)
            for position in effective_portfolio.positions
        }
        lengths = [len(series) for series in series_by_symbol.values() if series]
        common_length = min(lengths) if lengths else 0

        if common_length == 0:
            portfolio_returns: list[float] = []
        else:
            portfolio_returns = []
            for index in range(-common_length, 0):
                portfolio_return = 0.0
                for position in effective_portfolio.positions:
                    series = series_by_symbol[position.symbol]
                    symbol_return = series[index] if series else 0.0
                    portfolio_return += position.weight * symbol_return
                portfolio_returns.append(portfolio_return)

        volatility = pstdev(portfolio_returns) * math.sqrt(252) if len(portfolio_returns) > 1 else 0.0
        value_at_risk_95 = self._historical_var(portfolio_returns, 0.95)
        max_drawdown = self._max_drawdown(portfolio_returns)
        rolling_return_1d = self._rolling_return(portfolio_returns, window=24)

        snapshot = RiskSnapshot(
            snapshot_id=make_prefixed_id("risk"),
            portfolio_id=effective_portfolio.portfolio_id,
            volatility=round(volatility, 6),
            value_at_risk_95=round(value_at_risk_95, 6),
            max_drawdown=round(max_drawdown, 6),
            rolling_return_1d=round(rolling_return_1d, 6),
        )
        self.snapshots.append(snapshot)

        record_ledger_event(
            self.ledger_appender,
            event_type="risk_snapshot_computed",
            actor_node=self.node_id,
            payload=snapshot.model_dump(),
        )
        self._save_state()
        return snapshot

    def get_portfolio(self) -> Portfolio | None:
        return self.portfolio

    def latest_snapshot(self) -> RiskSnapshot | None:
        return self.snapshots[-1] if self.snapshots else None

    def snapshot_history(self) -> list[RiskSnapshot]:
        return list(self.snapshots)

    def health(self) -> dict[str, object]:
        return {
            "status": "ok",
            "service": "gcp_risk",
            "node_id": self.node_id,
            "symbols_tracked": len(self.events_by_symbol),
            "portfolio_loaded": self.portfolio is not None,
            "snapshots": len(self.snapshots),
        }

    def _returns_for_symbol(self, symbol: str) -> list[float]:
        prices = [event.price for event in self.events_by_symbol.get(symbol, [])]
        return [
            ((prices[index] - prices[index - 1]) / prices[index - 1])
            for index in range(1, len(prices))
            if prices[index - 1]
        ]

    @staticmethod
    def _historical_var(returns: list[float], confidence: float) -> float:
        if not returns:
            return 0.0
        sorted_returns = sorted(returns)
        tail_index = max(0, min(len(sorted_returns) - 1, int((1 - confidence) * len(sorted_returns))))
        return sorted_returns[tail_index]

    @staticmethod
    def _max_drawdown(returns: list[float]) -> float:
        if not returns:
            return 0.0

        equity_curve = []
        running = 1.0
        for item in returns:
            running *= 1 + item
            equity_curve.append(running)

        peak = equity_curve[0]
        max_drawdown = 0.0
        for value in equity_curve:
            peak = max(peak, value)
            drawdown = (value - peak) / peak
            max_drawdown = min(max_drawdown, drawdown)
        return max_drawdown

    @staticmethod
    def _rolling_return(returns: list[float], window: int) -> float:
        if not returns:
            return 0.0
        selected = returns[-window:]
        result = 1.0
        for item in selected:
            result *= 1 + item
        return result - 1

    def _load_state(self) -> None:
        payload = load_json_file(self.state_path, {"events_by_symbol": {}, "portfolio": None, "snapshots": []})
        self.events_by_symbol = defaultdict(list)
        for symbol, events in payload.get("events_by_symbol", {}).items():
            self.events_by_symbol[symbol] = [MarketEvent.model_validate(item) for item in events]
        portfolio_payload = payload.get("portfolio")
        self.portfolio = Portfolio.model_validate(portfolio_payload) if portfolio_payload else None
        self.snapshots = [RiskSnapshot.model_validate(item) for item in payload.get("snapshots", [])]

    def _save_state(self) -> None:
        save_json_file(
            self.state_path,
            {
                "events_by_symbol": {
                    symbol: [event.model_dump() for event in events]
                    for symbol, events in self.events_by_symbol.items()
                },
                "portfolio": self.portfolio.model_dump() if self.portfolio is not None else None,
                "snapshots": [snapshot.model_dump() for snapshot in self.snapshots],
            },
        )
