from __future__ import annotations

import json
import logging
import ssl
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import urlparse

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)

MessageHandler = Callable[[str, dict[str, Any]], None]


@dataclass(slots=True)
class MqttConfig:
    host: str
    port: int
    tls: bool = False
    username: str | None = None
    password: str | None = None
    keepalive: int = 30
    client_id_prefix: str = "quantian"


def parse_broker_url(url: str) -> MqttConfig:
    parsed = urlparse(url)
    scheme = (parsed.scheme or "mqtt").lower()
    tls = scheme in ("mqtts", "ssl")
    host = parsed.hostname or "localhost"
    port = parsed.port or (8883 if tls else 1883)
    return MqttConfig(
        host=host,
        port=port,
        tls=tls,
        username=parsed.username,
        password=parsed.password,
    )


class MqttPublisher:
    def __init__(self, config: MqttConfig, *, client_id: str | None = None) -> None:
        self.config = config
        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id or f"{config.client_id_prefix}-pub",
        )
        if config.username:
            self._client.username_pw_set(config.username, config.password)
        if config.tls:
            self._client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
        self._connected = False

    def connect(self) -> None:
        if self._connected:
            return
        self._client.connect(self.config.host, self.config.port, keepalive=self.config.keepalive)
        self._client.loop_start()
        self._connected = True

    def publish(self, topic: str, payload: dict[str, Any], *, qos: int = 1) -> None:
        if not self._connected:
            self.connect()
        body = json.dumps(payload).encode("utf-8")
        info = self._client.publish(topic, body, qos=qos)
        info.wait_for_publish(timeout=5.0)

    def disconnect(self) -> None:
        if not self._connected:
            return
        self._client.loop_stop()
        self._client.disconnect()
        self._connected = False

    def __enter__(self) -> "MqttPublisher":
        self.connect()
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.disconnect()


class MqttSubscriber:
    def __init__(
        self,
        config: MqttConfig,
        topics: list[str],
        handler: MessageHandler,
        *,
        client_id: str | None = None,
    ) -> None:
        self.config = config
        self.topics = topics
        self.handler = handler
        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id or f"{config.client_id_prefix}-sub",
        )
        if config.username:
            self._client.username_pw_set(config.username, config.password)
        if config.tls:
            self._client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self.messages_received = 0
        self.messages_handled = 0
        self.handler_errors = 0

    def _on_connect(self, client: mqtt.Client, _userdata: Any, _flags: Any, reason_code: Any, _props: Any) -> None:
        if getattr(reason_code, "is_failure", False):
            logger.warning("mqtt subscriber connect failed: %s", reason_code)
            return
        for topic in self.topics:
            client.subscribe(topic, qos=1)
            logger.info("mqtt subscribed to %s", topic)

    def _on_message(self, _client: mqtt.Client, _userdata: Any, message: mqtt.MQTTMessage) -> None:
        self.messages_received += 1
        try:
            payload = json.loads(message.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self.handler_errors += 1
            logger.warning("mqtt payload parse failed on %s: %s", message.topic, exc)
            return

        try:
            self.handler(message.topic, payload)
            self.messages_handled += 1
        except Exception as exc:
            self.handler_errors += 1
            logger.exception("mqtt handler error on %s: %s", message.topic, exc)

    def start(self) -> None:
        self._client.connect(self.config.host, self.config.port, keepalive=self.config.keepalive)
        self._client.loop_start()

    def stop(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()

    def stats(self) -> dict[str, int]:
        return {
            "received": self.messages_received,
            "handled": self.messages_handled,
            "errors": self.handler_errors,
        }
