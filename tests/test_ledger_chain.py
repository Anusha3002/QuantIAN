from __future__ import annotations

from registry_service.store import InMemoryRegistryStore
from shared.schemas import LedgerAppendRequest


def _append(store: InMemoryRegistryStore, event_type: str, payload: dict | None = None) -> None:
    store.append_block(
        LedgerAppendRequest(
            event_type=event_type,
            actor_node="tester",
            payload=payload or {},
        )
    )


def test_fresh_ledger_verifies_as_empty(tmp_path) -> None:
    store = InMemoryRegistryStore(state_dir=tmp_path)
    result = store.verify_ledger()
    assert result.valid
    assert result.block_count == 0


def test_appended_chain_links_previous_hash(tmp_path) -> None:
    store = InMemoryRegistryStore(state_dir=tmp_path)
    _append(store, "evt_a")
    _append(store, "evt_b")
    _append(store, "evt_c")
    blocks = store.list_blocks()
    assert len(blocks) == 3
    assert blocks[0].previous_hash is None
    assert blocks[1].previous_hash == blocks[0].block_hash
    assert blocks[2].previous_hash == blocks[1].block_hash


def test_verify_detects_payload_hash_tamper(tmp_path) -> None:
    store = InMemoryRegistryStore(state_dir=tmp_path)
    _append(store, "evt_a", {"x": 1})
    _append(store, "evt_b", {"x": 2})
    _append(store, "evt_c", {"x": 3})

    # tamper with an earlier block's payload_hash directly
    store._ledger[1] = store._ledger[1].model_copy(update={"payload_hash": "sha256:tampered"})
    result = store.verify_ledger()
    assert not result.valid
    assert result.error is not None


def test_verify_detects_broken_previous_hash(tmp_path) -> None:
    store = InMemoryRegistryStore(state_dir=tmp_path)
    _append(store, "evt_a")
    _append(store, "evt_b")
    # shuffle the previous_hash pointer
    store._ledger[1] = store._ledger[1].model_copy(update={"previous_hash": "sha256:wrong"})
    result = store.verify_ledger()
    assert not result.valid


def test_peer_capability_discovery(tmp_path) -> None:
    from shared.schemas import PeerRegistration

    store = InMemoryRegistryStore(state_dir=tmp_path)
    peer_a = PeerRegistration(
        node_id="peer-a",
        node_type="ingestion",
        cloud="aws",
        base_url="http://a",
        capabilities=["ingest_market_data", "publish_events"],
    )
    peer_b = PeerRegistration(
        node_id="peer-b",
        node_type="anomaly",
        cloud="azure",
        base_url="http://b",
        capabilities=["detect_anomalies"],
    )
    store.upsert_peer(peer_a)
    store.upsert_peer(peer_b)

    matches = store.peers_with_capability("detect_anomalies")
    assert [p.node_id for p in matches] == ["peer-b"]

    matches_pub = store.peers_with_capability("publish_events")
    assert [p.node_id for p in matches_pub] == ["peer-a"]
