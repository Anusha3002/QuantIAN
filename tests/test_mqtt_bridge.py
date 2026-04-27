from __future__ import annotations

import json
from unittest.mock import MagicMock

from iot.bridge import DEFAULT_TOPIC, MqttIngestionBridge, topic_for
from iot.mqtt_client import MqttConfig, parse_broker_url


def test_parse_broker_url_defaults_to_1883() -> None:
    config = parse_broker_url("mqtt://broker")
    assert config.host == "broker"
    assert config.port == 1883
    assert config.tls is False


def test_parse_broker_url_tls_defaults_to_8883() -> None:
    config = parse_broker_url("mqtts://example.com")
    assert config.tls is True
    assert config.port == 8883


def test_topic_for_uses_hierarchy() -> None:
    assert topic_for("BTCUSD", asset_class="crypto") == "quantian/market/crypto/BTCUSD"


def test_bridge_forwards_valid_message(monkeypatch) -> None:
    config = MqttConfig(host="localhost", port=1883)
    bridge = MqttIngestionBridge(mqtt_config=config, ingestion_url="http://ingest.local")

    posted: list = []

    class StubResponse:
        def raise_for_status(self) -> None:
            return None

    stub_client = MagicMock()
    stub_client.post = lambda url, json: (posted.append({"url": url, "payload": json}), StubResponse())[1]
    bridge._http = stub_client  # swap in our stub

    payload = {
        "sensor_id": "sensor-btc",
        "symbol": "BTCUSD",
        "asset_class": "crypto",
        "price": 68000.0,
        "volume": 120000.0,
        "source": "test",
    }
    bridge._handle_message("quantian/market/crypto/BTCUSD", payload)

    assert bridge.forwarded == 1
    assert bridge.validation_failures == 0
    assert len(posted) == 1
    assert posted[0]["url"] == "http://ingest.local/ingestion/messages"
    assert posted[0]["payload"]["symbol"] == "BTCUSD"


def test_bridge_rejects_invalid_payload() -> None:
    config = MqttConfig(host="localhost", port=1883)
    bridge = MqttIngestionBridge(mqtt_config=config, ingestion_url="http://ingest.local")

    bridge._handle_message("quantian/market/garbage/X", {"not": "valid"})

    assert bridge.forwarded == 0
    assert bridge.validation_failures == 1


def test_default_topic_matches_symbol_hierarchy() -> None:
    # Default topic "quantian/market/+/+" should match "quantian/market/crypto/BTCUSD"
    # (structural check, not MQTT wildcard matching — just that depth matches)
    assert DEFAULT_TOPIC.count("/") == topic_for("BTCUSD", asset_class="crypto").count("/")
