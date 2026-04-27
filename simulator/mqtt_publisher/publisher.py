from __future__ import annotations

import logging
import time
from typing import Iterable

from iot.bridge import topic_for
from iot.mqtt_client import MqttConfig, MqttPublisher
from simulator.mqtt_publisher.generator import MarketSensorSimulator

logger = logging.getLogger(__name__)


class SimulatedMarketPublisher:
    """Drives the MarketSensorSimulator and publishes each tick over MQTT.

    This is the edge producer side of the IoT pillar: simulated sensors emit
    market ticks onto an MQTT broker; the IoT bridge subscribes and forwards
    them into the cloud ingestion peer.
    """

    def __init__(
        self,
        *,
        mqtt_config: MqttConfig,
        simulator: MarketSensorSimulator | None = None,
        client_id: str = "quantian-sim",
    ) -> None:
        self.simulator = simulator or MarketSensorSimulator()
        self._publisher = MqttPublisher(mqtt_config, client_id=client_id)
        self.published = 0

    def publish_cycle(self, *, anomaly_symbol: str | None = None, symbols: Iterable[str] | None = None) -> int:
        messages = self.simulator.generate_cycle(
            symbols=list(symbols) if symbols is not None else None,
            anomaly_symbol=anomaly_symbol,
        )
        for message in messages:
            topic = topic_for(message.symbol, asset_class=message.asset_class)
            self._publisher.publish(topic, message.model_dump())
            self.published += 1
        return len(messages)

    def run(
        self,
        *,
        cycles: int,
        interval_seconds: float,
        anomaly_cycle: int | None = None,
        anomaly_symbol: str = "BTCUSD",
    ) -> int:
        self._publisher.connect()
        try:
            for cycle in range(cycles):
                current_anomaly = anomaly_symbol if cycle == anomaly_cycle else None
                self.publish_cycle(anomaly_symbol=current_anomaly)
                if cycle != cycles - 1 and interval_seconds > 0:
                    time.sleep(interval_seconds)
        finally:
            self._publisher.disconnect()
        return self.published
