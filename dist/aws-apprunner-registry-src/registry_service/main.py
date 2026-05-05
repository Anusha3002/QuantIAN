from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, status

from registry_service.store import InMemoryRegistryStore
from shared.schemas import (
    LedgerAppendRequest,
    LedgerBlock,
    LedgerVerificationResult,
    PeerHeartbeat,
    PeerRegistration,
)

logger = logging.getLogger(__name__)

store = InMemoryRegistryStore(
    state_dir=Path(os.getenv("QUANTIAN_DATA_DIR", str(Path.cwd() / "data" / "runtime"))) / "registry_service"
)

LEDGER_VERIFY_INTERVAL_SECONDS = int(os.getenv("LEDGER_VERIFY_INTERVAL_SECONDS", "60"))
_verification_state: dict[str, object] = {
    "last_result": None,
    "last_checked_at": None,
    "runs": 0,
    "failures": 0,
}


async def _periodic_verifier() -> None:
    while True:
        await asyncio.sleep(max(5, LEDGER_VERIFY_INTERVAL_SECONDS))
        try:
            result = store.verify_ledger()
            _verification_state["runs"] = int(_verification_state.get("runs", 0)) + 1
            _verification_state["last_result"] = result.model_dump()
            from shared.utils.time import utc_now

            _verification_state["last_checked_at"] = utc_now()
            if not result.valid:
                _verification_state["failures"] = int(_verification_state.get("failures", 0)) + 1
                logger.error("ledger verification failed: %s", result.error)
                store.append_block(
                    LedgerAppendRequest(
                        event_type="ledger_verification_failed",
                        actor_node="registry_service",
                        payload={"error": result.error or "unknown", "block_count": result.block_count},
                    )
                )
            else:
                logger.info(
                    "ledger verified: %s blocks intact", result.block_count
                )
        except Exception as exc:  # pragma: no cover
            logger.warning("ledger verifier loop error: %s", exc)


@asynccontextmanager
async def lifespan(_: FastAPI):
    verifier_task = asyncio.create_task(_periodic_verifier())
    try:
        yield
    finally:
        verifier_task.cancel()
        try:
            await verifier_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="QuantIAN Registry Service", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "registry_service",
        "peers": len(store.list_peers()),
        "ledger_blocks": len(store.list_blocks()),
        "peer_counts": store.peer_counts(),
        "ledger_verifier": {
            "interval_seconds": LEDGER_VERIFY_INTERVAL_SECONDS,
            "runs": _verification_state.get("runs", 0),
            "failures": _verification_state.get("failures", 0),
            "last_checked_at": _verification_state.get("last_checked_at"),
            "last_result": _verification_state.get("last_result"),
        },
    }


@app.post("/registry/peers", response_model=PeerRegistration, status_code=status.HTTP_201_CREATED)
def register_peer(peer: PeerRegistration) -> PeerRegistration:
    registered = store.upsert_peer(peer)
    store.append_block(
        LedgerAppendRequest(
            event_type="peer_registered",
            actor_node=registered.node_id,
            payload=registered.model_dump(),
        )
    )
    return registered


@app.post("/registry/peers/{node_id}/heartbeat", response_model=PeerRegistration)
def peer_heartbeat(node_id: str, heartbeat: PeerHeartbeat) -> PeerRegistration:
    updated = store.heartbeat(node_id, heartbeat)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="peer not found")

    store.append_block(
        LedgerAppendRequest(
            event_type="peer_heartbeat",
            actor_node=node_id,
            payload=heartbeat.model_dump(),
        )
    )
    return updated


@app.get("/registry/peers", response_model=list[PeerRegistration])
def list_peers() -> list[PeerRegistration]:
    return store.list_peers()


@app.get("/registry/peers/{node_id}", response_model=PeerRegistration)
def get_peer(node_id: str) -> PeerRegistration:
    peer = store.get_peer(node_id)
    if peer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="peer not found")
    return peer


@app.get("/registry/capabilities/{capability}", response_model=list[PeerRegistration])
def peers_by_capability(capability: str) -> list[PeerRegistration]:
    return store.peers_with_capability(capability)


@app.post("/ledger/blocks", response_model=LedgerBlock, status_code=status.HTTP_201_CREATED)
def append_block(request: LedgerAppendRequest) -> LedgerBlock:
    return store.append_block(request)


@app.get("/ledger/blocks", response_model=list[LedgerBlock])
def list_blocks() -> list[LedgerBlock]:
    return store.list_blocks()


@app.get("/ledger/verify", response_model=LedgerVerificationResult)
def verify_ledger() -> LedgerVerificationResult:
    return store.verify_ledger()
