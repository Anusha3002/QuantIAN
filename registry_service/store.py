from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from shared.schemas import (
    LedgerAppendRequest,
    LedgerBlock,
    LedgerVerificationResult,
    PeerHeartbeat,
    PeerRegistration,
    PeerStatus,
)
from shared.storage import load_json_file, save_json_file
from shared.utils.hashing import hash_json
from shared.utils.time import utc_now


class InMemoryRegistryStore:
    def __init__(self, state_dir: str | Path | None = None) -> None:
        self._lock = Lock()
        self._state_dir = Path(state_dir) if state_dir is not None else None
        self._peers: dict[str, PeerRegistration] = {}
        self._ledger: list[LedgerBlock] = []
        self._load_state()

    def upsert_peer(self, peer: PeerRegistration) -> PeerRegistration:
        with self._lock:
            normalized = peer.model_copy(update={"status": PeerStatus.ONLINE, "last_heartbeat": utc_now()})
            self._peers[peer.node_id] = normalized
            self._save_state()
            return normalized

    def heartbeat(self, node_id: str, heartbeat: PeerHeartbeat) -> PeerRegistration | None:
        with self._lock:
            peer = self._peers.get(node_id)
            if peer is None:
                return None

            updated = peer.model_copy(
                update={
                    "status": heartbeat.status,
                    "last_heartbeat": heartbeat.observed_at,
                }
            )
            self._peers[node_id] = updated
            self._save_state()
            return updated

    def list_peers(self) -> list[PeerRegistration]:
        with self._lock:
            return [self._with_fresh_status(peer) for peer in self._peers.values()]

    def get_peer(self, node_id: str) -> PeerRegistration | None:
        with self._lock:
            peer = self._peers.get(node_id)
            if peer is None:
                return None
            return self._with_fresh_status(peer)

    def peers_with_capability(self, capability: str) -> list[PeerRegistration]:
        with self._lock:
            matching = [peer for peer in self._peers.values() if capability in peer.capabilities]
            return [self._with_fresh_status(peer) for peer in matching]

    def append_block(self, request: LedgerAppendRequest) -> LedgerBlock:
        with self._lock:
            previous_hash = self._ledger[-1].block_hash if self._ledger else None
            block = LedgerBlock(
                block_id=len(self._ledger) + 1,
                timestamp=utc_now(),
                event_type=request.event_type,
                actor_node=request.actor_node,
                payload_hash=hash_json(request.payload),
                previous_hash=previous_hash,
                block_hash="",
            )
            block = block.model_copy(update={"block_hash": self._compute_block_hash(block)})
            self._ledger.append(block)
            self._save_state()
            return block

    def list_blocks(self) -> list[LedgerBlock]:
        with self._lock:
            return list(self._ledger)

    def verify_ledger(self) -> LedgerVerificationResult:
        with self._lock:
            previous_hash: str | None = None
            for block in self._ledger:
                expected_hash = self._compute_block_hash(block)
                if block.previous_hash != previous_hash:
                    return LedgerVerificationResult(
                        valid=False,
                        block_count=len(self._ledger),
                        error=f"block {block.block_id} has invalid previous_hash",
                    )
                if block.block_hash != expected_hash:
                    return LedgerVerificationResult(
                        valid=False,
                        block_count=len(self._ledger),
                        error=f"block {block.block_id} hash mismatch",
                    )
                previous_hash = block.block_hash

            return LedgerVerificationResult(valid=True, block_count=len(self._ledger))

    def peer_counts(self) -> dict[str, int]:
        counts = {"online": 0, "stale": 0, "offline": 0}
        for peer in self.list_peers():
            counts[peer.status.value] += 1
        return counts

    def _with_fresh_status(self, peer: PeerRegistration) -> PeerRegistration:
        age_seconds = self._seconds_since(peer.last_heartbeat)
        if age_seconds > 180:
            status = PeerStatus.OFFLINE
        elif age_seconds > 90:
            status = PeerStatus.STALE
        else:
            status = PeerStatus.ONLINE
        return peer.model_copy(update={"status": status})

    @staticmethod
    def _compute_block_hash(block: LedgerBlock) -> str:
        return hash_json(
            {
                "block_id": block.block_id,
                "timestamp": block.timestamp,
                "event_type": block.event_type,
                "actor_node": block.actor_node,
                "payload_hash": block.payload_hash,
                "previous_hash": block.previous_hash,
            }
        )

    @staticmethod
    def _seconds_since(timestamp: str) -> float:
        observed_at = datetime.fromisoformat(timestamp)
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - observed_at).total_seconds())

    def _load_state(self) -> None:
        if self._state_dir is None:
            return

        peers_payload = load_json_file(self._state_dir / "peers.json", [])
        ledger_payload = load_json_file(self._state_dir / "ledger.json", [])
        self._peers = {
            item["node_id"]: PeerRegistration.model_validate(item)
            for item in peers_payload
        }
        self._ledger = [LedgerBlock.model_validate(item) for item in ledger_payload]

    def _save_state(self) -> None:
        if self._state_dir is None:
            return

        save_json_file(
            self._state_dir / "peers.json",
            [peer.model_dump() for peer in self._peers.values()],
        )
        save_json_file(
            self._state_dir / "ledger.json",
            [block.model_dump() for block in self._ledger],
        )
