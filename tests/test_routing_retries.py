from __future__ import annotations

from unittest.mock import MagicMock

import httpx

from shared.config import ServiceSettings
from shared.runtime.service_runtime import ServiceRuntime
from shared.schemas import PeerRegistration


def _runtime() -> ServiceRuntime:
    settings = ServiceSettings(
        service_name="test",
        app_env="local",
        service_port=9999,
        service_host="127.0.0.1",
        base_url="http://127.0.0.1:9999",
        registry_url="http://127.0.0.1:0",  # won't be reached
        ledger_url="http://127.0.0.1:0",
        mqtt_broker_url="mqtt://localhost:1883",
        storage_backend="memory",
        data_dir="/tmp/qn-test",
        heartbeat_interval_seconds=15,
        request_timeout_seconds=0.5,
        enable_runtime=False,
        debug=False,
    )
    return ServiceRuntime(
        settings=settings,
        node_id="test-node",
        node_type="test",
        cloud="local",
        capabilities=["test"],
    )


def _peer() -> PeerRegistration:
    return PeerRegistration(
        node_id="target-node",
        node_type="anomaly",
        cloud="azure",
        base_url="http://127.0.0.1:0",
        capabilities=["detect_anomalies"],
    )


def test_retry_succeeds_after_transient_failure(monkeypatch) -> None:
    runtime = _runtime()

    call_counter = {"n": 0}

    class StubClient:
        def __init__(self, *_, **__) -> None:
            pass

        def __enter__(self) -> "StubClient":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def request(self, method: str, url: str, json=None):  # noqa: ANN001
            call_counter["n"] += 1
            if call_counter["n"] < 2:
                raise httpx.ConnectError("boom")
            response = MagicMock()
            response.raise_for_status = lambda: None
            response.content = b"{\"ok\": true}"
            response.json = lambda: {"ok": True}
            return response

    monkeypatch.setattr(httpx, "Client", StubClient)
    # prevent actual sleeping between attempts
    monkeypatch.setattr("shared.runtime.service_runtime.time.sleep", lambda _s: None)

    body, exc = runtime.route_with_retries(
        peer=_peer(),
        path="/anomaly/analyze",
        payload={"event_id": "e1"},
        event_type="event_routed_to_anomaly",
        backoff_seconds=0.0,
    )
    assert exc is None
    assert body == {"ok": True}
    assert call_counter["n"] == 2


def test_route_fails_after_all_retries(monkeypatch) -> None:
    runtime = _runtime()

    class StubClient:
        def __init__(self, *_, **__) -> None:
            pass

        def __enter__(self) -> "StubClient":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def request(self, method: str, url: str, json=None):  # noqa: ANN001
            raise httpx.ConnectError("never comes back")

    monkeypatch.setattr(httpx, "Client", StubClient)
    monkeypatch.setattr("shared.runtime.service_runtime.time.sleep", lambda _s: None)

    # record ledger appends made via runtime.append_ledger
    appended: list = []
    runtime.append_ledger = lambda req: appended.append(req) or None  # type: ignore[assignment]

    body, exc = runtime.route_with_retries(
        peer=_peer(),
        path="/anomaly/analyze",
        payload=None,
        event_type="event_routed_to_anomaly",
        retries=3,
        backoff_seconds=0.0,
    )
    assert body is None
    assert exc is not None
    # one routing_failed ledger record on final failure
    assert len(appended) == 1
    assert appended[0].event_type == "routing_failed"
    assert appended[0].payload["attempts"] == 3
    assert appended[0].payload["target_node"] == "target-node"
