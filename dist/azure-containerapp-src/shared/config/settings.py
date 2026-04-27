from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ServiceSettings:
    service_name: str
    app_env: str
    service_port: int
    service_host: str
    base_url: str
    registry_url: str
    ledger_url: str
    mqtt_broker_url: str
    storage_backend: str
    data_dir: str
    heartbeat_interval_seconds: int
    request_timeout_seconds: float
    enable_runtime: bool
    debug: bool


def load_service_settings(service_name: str, default_port: int) -> ServiceSettings:
    service_prefix = service_name.upper().replace("-", "_")
    host = os.getenv("SERVICE_HOST", "0.0.0.0")
    port = int(os.getenv(f"{service_prefix}_PORT", os.getenv("SERVICE_PORT", default_port)))
    base_url = os.getenv(
        f"{service_prefix}_BASE_URL",
        os.getenv("BASE_URL", f"http://localhost:{port}"),
    )

    return ServiceSettings(
        service_name=service_name,
        app_env=os.getenv("APP_ENV", "local"),
        service_port=port,
        service_host=host,
        base_url=base_url,
        registry_url=os.getenv("REGISTRY_URL", "http://localhost:8000"),
        ledger_url=os.getenv("LEDGER_URL", os.getenv("REGISTRY_URL", "http://localhost:8000")),
        mqtt_broker_url=os.getenv("MQTT_BROKER_URL", "mqtt://localhost:1883"),
        storage_backend=os.getenv("STORAGE_BACKEND", "memory"),
        data_dir=str(
            Path(
                os.getenv("QUANTIAN_DATA_DIR", str(Path.cwd() / "data" / "runtime"))
            ).joinpath(service_name)
        ),
        heartbeat_interval_seconds=int(os.getenv("HEARTBEAT_INTERVAL_SECONDS", "15")),
        request_timeout_seconds=float(os.getenv("REQUEST_TIMEOUT_SECONDS", "2.5")),
        enable_runtime=os.getenv("ENABLE_SERVICE_RUNTIME", "true").lower() == "true",
        debug=os.getenv("DEBUG", "false").lower() == "true",
    )
