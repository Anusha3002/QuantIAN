from __future__ import annotations

import math

import pytest

from gcp_risk.service import RiskService
from shared.schemas import MarketEvent, Portfolio, PortfolioPosition


def _event(symbol: str, price: float, event_id: str = "evt") -> MarketEvent:
    return MarketEvent(
        event_id=event_id,
        symbol=symbol,
        asset_class="equity",
        price=price,
        volume=1000.0,
        source="test",
    )


def test_returns_calculated_from_price_series(tmp_path) -> None:
    service = RiskService(node_id="test-risk", state_path=tmp_path / "state.json")
    prices = [100.0, 110.0, 99.0, 121.0]
    for i, price in enumerate(prices):
        service.ingest_event(_event("AAA", price, event_id=f"evt-{i}"))

    returns = service._returns_for_symbol("AAA")
    expected = [0.10, -0.10, 22.0 / 99.0]
    assert returns == pytest.approx(expected, rel=1e-6)


def test_historical_var_picks_tail(tmp_path) -> None:
    returns = [-0.05, -0.03, -0.02, 0.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06]
    var_95 = RiskService._historical_var(returns, 0.95)
    # 5% tail of 10 observations -> index 0 after sort (= -0.05)
    assert var_95 == pytest.approx(-0.05)


def test_historical_var_empty_returns_zero() -> None:
    assert RiskService._historical_var([], 0.95) == 0.0


def test_max_drawdown_known_series() -> None:
    # +10%, -20% -> peak 1.10, trough 0.88 -> drawdown = (0.88 - 1.10)/1.10 = -0.20
    returns = [0.10, -0.20]
    drawdown = RiskService._max_drawdown(returns)
    assert drawdown == pytest.approx(-0.20, rel=1e-6)


def test_max_drawdown_monotonic_up_is_zero() -> None:
    assert RiskService._max_drawdown([0.01, 0.02, 0.03, 0.04]) == 0.0


def test_rolling_return_compounds_tail_window() -> None:
    # last-2 window on [r1, r2, r3] compounds (1+r2)(1+r3)-1
    returns = [0.5, 0.10, 0.20]
    assert RiskService._rolling_return(returns, window=2) == pytest.approx(0.10 * 0.20 + 0.10 + 0.20, rel=1e-9)


def test_compute_risk_annualized_volatility_scales_sqrt_252(tmp_path) -> None:
    service = RiskService(node_id="test-risk", state_path=tmp_path / "state.json")
    # alternating +1% / -1% gives large periodic stdev, easy to reason about
    price = 100.0
    for i in range(10):
        price *= 1.01 if i % 2 == 0 else 0.99
        service.ingest_event(_event("AAA", price, event_id=f"evt-{i}"))

    portfolio = Portfolio(
        portfolio_id="p1",
        positions=[PortfolioPosition(symbol="AAA", weight=1.0)],
    )
    snapshot = service.compute_risk(portfolio)

    # population stdev of the return series, scaled by sqrt(252)
    from statistics import pstdev

    returns = service._returns_for_symbol("AAA")
    expected = pstdev(returns) * math.sqrt(252)
    assert snapshot.volatility == pytest.approx(round(expected, 6))


def test_compute_risk_requires_portfolio(tmp_path) -> None:
    service = RiskService(node_id="test-risk", state_path=tmp_path / "state.json")
    with pytest.raises(ValueError):
        service.compute_risk()
