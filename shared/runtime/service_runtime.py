from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

from shared.config import ServiceSettings
from shared.schemas import LedgerAppendRequest, PeerRegistration

logger = logging.getLogger(__name__)

DEFAULT_ROUTE_RETRIES = 3
DEFAULT_ROUTE_BACKOFF_SECONDS = 0.25


class ServiceRuntime:
    def __init__(
        self,
        *,
        settings: ServiceSettings,
        node_id: str,
        node_type: str,
        cloud: str,
        capabilities: list[str],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.settings = settings
        self.node_id = node_id
        self.node_type = node_type
        self.cloud = cloud
        self.capabilities = capabilities
        self.metadata = metadata or {}
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._registered = False

    async def start(self) -> None:
        if not self.settings.enable_runtime:
            return
        await self._register_or_heartbeat()
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def stop(self) -> None:
        if self._heartbeat_task is None:
            return
        self._heartbeat_task.cancel()
        try:
            await self._heartbeat_task
        except asyncio.CancelledError:
            pass

    def peer_registration(self) -> PeerRegistration:
        return PeerRegistration(
            node_id=self.node_id,
            node_type=self.node_type,
            cloud=self.cloud,
            base_url=self.settings.base_url,
            capabilities=self.capabilities,
            metadata=self.metadata,
        )

    def peers_by_capability(self, capability: str) -> list[PeerRegistration]:
        if not self.settings.enable_runtime:
            return []

        response = self._request_json("GET", f"{self.settings.registry_url}/registry/capabilities/{capability}")
        if not isinstance(response, list):
            return []
        return [PeerRegistration.model_validate(item) for item in response]

    def append_ledger(self, request: Any) -> object | None:
        if not self.settings.enable_runtime:
            return None
        return self._request_json(
            "POST",
            f"{self.settings.ledger_url}/ledger/blocks",
            json=request.model_dump(),
        )

    def post_json(self, base_url: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        return self._request_json("POST", f"{base_url}{path}", json=payload)

    def route_with_retries(
        self,
        *,
        peer: PeerRegistration,
        path: str,
        payload: dict[str, Any] | None,
        event_type: str,
        ledger_context: dict[str, Any] | None = None,
        retries: int = DEFAULT_ROUTE_RETRIES,
        backoff_seconds: float = DEFAULT_ROUTE_BACKOFF_SECONDS,
    ) -> tuple[Any, Exception | None]:
        """POST to a peer with retries + exponential backoff.

        On final failure, records a `routing_failed` block to the ledger so silent
        drops become auditable. Returns (response_or_None, exception_or_None).
        """
        url = f"{peer.base_url}{path}"
        last_exc: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                with httpx.Client(timeout=self.settings.request_timeout_seconds) as client:
                    response = client.request("POST", url, json=payload)
                    response.raise_for_status()
                    body = response.json() if response.content else None
                    if attempt > 1:
                        logger.info(
                            "routing %s to %s succeeded on attempt %d", event_type, peer.node_id, attempt
                        )
                    return body, None
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "route %s -> %s attempt %d/%d failed: %s",
                    event_type,
                    peer.node_id,
                    attempt,
                    retries,
                    exc,
                )
                if attempt < retries:
                    time.sleep(backoff_seconds * (2 ** (attempt - 1)))

        context = ledger_context or {}
        failure_payload = {
            **context,
            "target_node": peer.node_id,
            "target_url": url,
            "event_type": event_type,
            "attempts": retries,
            "error": str(last_exc) if last_exc else "unknown",
        }
        try:
            self.append_ledger(
                LedgerAppendRequest(
                    event_type="routing_failed",
                    actor_node=self.node_id,
                    payload=failure_payload,
                )
            )
        except Exception as ledger_exc:  # pragma: no cover
            logger.warning("failed to record routing_failed block: %s", ledger_exc)

        return None, last_exc

    async def _heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(self.settings.heartbeat_interval_seconds)
            await self._register_or_heartbeat()

    async def _register_or_heartbeat(self) -> None:
        try:
            async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
                if not self._registered:
                    response = await client.post(
                        f"{self.settings.registry_url}/registry/peers",
                        json=self.peer_registration().model_dump(),
                    )
                    response.raise_for_status()
                    self._registered = True
                    return

                response = await client.post(
                    f"{self.settings.registry_url}/registry/peers/{self.node_id}/heartbeat",
                    json={},
                )
                response.raise_for_status()
        except Exception as exc:  # pragma: no cover
            self._registered = False
            logger.warning("runtime registry interaction failed for %s: %s", self.node_id, exc)

    def _request_json(self, method: str, url: str, *, json: dict[str, Any] | None = None) -> Any:
        try:
            with httpx.Client(timeout=self.settings.request_timeout_seconds) as client:
                response = client.request(method, url, json=json)
                response.raise_for_status()
                if not response.content:
                    return None
                return response.json()
        except Exception as exc:  # pragma: no cover
            logger.warning("runtime request failed %s %s: %s", method, url, exc)
            return None
