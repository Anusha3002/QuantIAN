from __future__ import annotations

from random import Random

from shared.schemas import MarketSensorMessage


class MarketSensorSimulator:
    def __init__(self, *, seed: int = 42) -> None:
        self.random = Random(seed)
        self._state = {
            "BTCUSD": {"price": 68000.0, "volume": 120000.0, "asset_class": "crypto"},
            "ETHUSD": {"price": 3200.0, "volume": 210000.0, "asset_class": "crypto"},
            "AAPL": {"price": 210.0, "volume": 1500000.0, "asset_class": "equity"},
            "MSFT": {"price": 430.0, "volume": 1100000.0, "asset_class": "equity"},
        }

    def next_message(self, symbol: str, *, inject_anomaly: bool = False) -> MarketSensorMessage:
        state = self._state[symbol]
        price_shift = self.random.uniform(-0.007, 0.007)
        volume_shift = self.random.uniform(-0.12, 0.12)

        if inject_anomaly:
            price_shift += 0.08 if self.random.random() >= 0.5 else -0.08
            volume_shift += 0.45

        state["price"] = round(max(0.01, state["price"] * (1 + price_shift)), 6)
        state["volume"] = round(max(1.0, state["volume"] * (1 + volume_shift)), 6)

        return MarketSensorMessage(
            sensor_id=f"sensor-{symbol.lower()}",
            symbol=symbol,
            asset_class=state["asset_class"],
            price=state["price"],
            volume=state["volume"],
            source="market-simulator",
        )

    def generate_cycle(
        self,
        *,
        symbols: list[str] | None = None,
        anomaly_symbol: str | None = None,
    ) -> list[MarketSensorMessage]:
        selected = symbols or list(self._state)
        return [
            self.next_message(symbol, inject_anomaly=(symbol == anomaly_symbol))
            for symbol in selected
        ]
