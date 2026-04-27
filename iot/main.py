from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from iot.bridge import DEFAULT_TOPIC, MqttIngestionBridge
from iot.mqtt_client import parse_broker_url
from shared.config import load_service_settings
from shared.runtime import ServiceRuntime

logging.basicConfig(level=logging.INFO)

settings = load_service_settings("iot_bridge", 8004)

INGESTION_URL = os.getenv("AWS_INGESTION_URL", "http://localhost:8001")
MQTT_TOPICS = [topic.strip() for topic in os.getenv("MQTT_TOPICS", DEFAULT_TOPIC).split(",") if topic.strip()]

bridge = MqttIngestionBridge(
    mqtt_config=parse_broker_url(settings.mqtt_broker_url),
    ingestion_url=INGESTION_URL,
    topics=MQTT_TOPICS,
)

runtime = ServiceRuntime(
    settings=settings,
    node_id="iot-bridge-01",
    node_type="iot_bridge",
    cloud="aws",
    capabilities=["collect_edge_telemetry", "mqtt_bridge"],
    metadata={"broker": settings.mqtt_broker_url, "topics": MQTT_TOPICS},
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        bridge.start()
    except Exception as exc:  # pragma: no cover - broker may not be available in local dev
        logging.warning("mqtt bridge failed to start: %s", exc)
    await runtime.start()
    yield
    await runtime.stop()
    try:
        bridge.stop()
    except Exception:  # pragma: no cover
        pass


app = FastAPI(title="QuantIAN IoT Bridge", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "iot_bridge",
        "node_id": "iot-bridge-01",
        "broker": settings.mqtt_broker_url,
        "topics": MQTT_TOPICS,
        "ingestion_url": INGESTION_URL,
        **bridge.stats(),
    }
