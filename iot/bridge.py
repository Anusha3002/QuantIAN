from __future__ import annotations

import logging
from typing import Any

import httpx

from iot.mqtt_client import MqttConfig, MqttSubscriber
from shared.schemas import MarketSensorMessage

logger = logging.getLogger(__name__)

DEFAULT_TOPIC = "quantian/market/+/+"


class MqttIngestionBridge:
    """Subscribes to MQTT market topics and forwards validated messages to the ingestion peer.

    Mirrors the AWS IoT Core Rule -> Lambda -> ingestion pattern: the broker is the edge
    collection point and the bridge is the glue that hands payloads to the cloud peer.
    """

    def __init__(
        self,
        *,
        mqtt_config: MqttConfig,
        ingestion_url: str,
        topics: list[str] | None = None,
        request_timeout: float = 5.0,
    ) -> None:
        self.ingestion_url = ingestion_url.rstrip("/")
        self.request_timeout = request_timeout
        self._http = httpx.Client(timeout=request_timeout)
        self.forwarded = 0
        self.forward_failures = 0
        self.validation_failures = 0
        self._subscriber = MqttSubscriber(
            mqtt_config,
            topics or [DEFAULT_TOPIC],
            handler=self._handle_message,
            client_id=f"{mqtt_config.client_id_prefix}-bridge",
        )

    def _handle_message(self, topic: str, payload: dict[str, Any]) -> None:
        try:
            message = MarketSensorMessage.model_validate(payload)
        except Exception as exc:
            self.validation_failures += 1
            logger.warning("invalid MarketSensorMessage on %s: %s", topic, exc)
            return

        try:
            response = self._http.post(
                f"{self.ingestion_url}/ingestion/messages",
                json=message.model_dump(),
            )
            response.raise_for_status()
            self.forwarded += 1
        except Exception as exc:
            self.forward_failures += 1
            logger.warning("forward to ingestion failed for %s/%s: %s", topic, message.symbol, exc)

    def start(self) -> None:
        self._subscriber.start()

    def stop(self) -> None:
        self._subscriber.stop()
        self._http.close()

    def stats(self) -> dict[str, int]:
        mqtt_stats = self._subscriber.stats()
        return {
            "mqtt_received": mqtt_stats["received"],
            "mqtt_handled": mqtt_stats["handled"],
            "mqtt_errors": mqtt_stats["errors"],
            "forwarded_to_ingestion": self.forwarded,
            "forward_failures": self.forward_failures,
            "validation_failures": self.validation_failures,
        }


def topic_for(symbol: str, *, asset_class: str = "market") -> str:
    return f"quantian/market/{asset_class}/{symbol}"
