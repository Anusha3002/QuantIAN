# QuantIAN P2P Overlay

## Summary

QuantIAN uses a **supernode-based hybrid P2P overlay** for cross-cloud peer
coordination, modeled on the Air Quality Analysis Platform precedent
(course project idea #13). Peers are independent services running on
different cloud providers (AWS, Azure, GCP). They do not address each other
by hard-coded URLs; instead they **discover each other at runtime** via a
shared registry supernode.

## Overlay Roles

| Role | Implementation | Responsibility |
|------|----------------|----------------|
| Supernode | `registry_service` (FastAPI) | Peer registration, capability index, heartbeat tracking, append-only ledger |
| Peer | `aws_ingestion`, `azure_anomaly`, `gcp_risk`, `iot_bridge` | Advertise capabilities, emit heartbeats, discover other peers by capability, route work |
| Bootstrap | `REGISTRY_URL` env var | Initial contact point every peer knows |

## Peer Lifecycle

```
        ┌──────────────────────────────────────────┐
        │           Registry (supernode)           │
        │   /registry/peers    /ledger/blocks      │
        └────────────────▲───────────┬─────────────┘
                         │ register  │ peer list
                         │ heartbeat │ by capability
              ┌──────────┴───────────▼──────────┐
              │                                 │
     ┌────────┴────────┐              ┌─────────┴────────┐
     │  aws_ingestion  │──route──────▶│ azure_anomaly    │
     │   (AWS peer)    │              │    (Azure peer)  │
     └────────┬────────┘              └─────────┬────────┘
              │                                 │
              └──────────────┬──────────────────┘
                             ▼
                    ┌──────────────────┐
                    │   gcp_risk       │
                    │   (GCP peer)     │
                    └──────────────────┘
```

1. **Register** — on startup, each peer POSTs `PeerRegistration` to
   `/registry/peers` with its `node_id`, `cloud`, `base_url`, and list of
   advertised `capabilities` (e.g. `detect_anomalies`, `compute_risk`,
   `collect_edge_telemetry`).
2. **Heartbeat** — every `HEARTBEAT_INTERVAL_SECONDS`, each peer POSTs to
   `/registry/peers/{node_id}/heartbeat`. The supernode flips stale peers
   (>90s) to `stale` and dead peers (>180s) to `offline`. Discovery queries
   always return a freshly-computed status.
3. **Discover** — before routing, a peer queries
   `/registry/capabilities/{capability}` and gets back the set of currently
   online peers that declare the capability. This is the core of the
   overlay: **no hard-coded URLs between peers**.
4. **Route** — peer calls the target peer's REST endpoint using the URL from
   the registry response and records the routing decision on the ledger.

## Ledger (append-only, hash-chained)

Every meaningful action in the overlay is appended to a ledger that lives on
the supernode:

- `peer_registered`, `peer_heartbeat`
- `market_event_ingested`, `event_routed_to_anomaly`, `event_routed_to_risk`
- `anomaly_alert_created`, `anomaly_alert_reviewed`
- `risk_snapshot_computed`
- `routing_failed` (introduced when cross-cloud routing gives up)
- `ledger_verification_failed` (self-recorded when auto-verification fails)

Each block is `SHA256(block_id, timestamp, event_type, actor_node,
payload_hash, previous_hash)`, which pins every block to the chain of blocks
before it. Tampering with any earlier block invalidates every block after
it.

### Auto-verification

The registry spawns a background task at startup
(`LEDGER_VERIFY_INTERVAL_SECONDS`, default 60s) that walks the chain and
recomputes every block hash. The result is exposed on `/health` under
`ledger_verifier` and on the explicit endpoint `/ledger/verify`. On a
failure, the registry **writes a `ledger_verification_failed` block** so the
audit trail captures its own tamper detection.

## How this maps to course requirements

| Pillar | QuantIAN realization |
|--------|----------------------|
| Multi-cloud PaaS | 3 peers on AWS / Azure / GCP |
| Machine Learning | `azure_anomaly` hybrid: rule-based + Isolation Forest |
| IoT | `iot_bridge` subscribes to MQTT, forwards to ingestion peer |
| P2P / Blockchain | Supernode overlay + hash-chained append-only ledger with self-auditing |

## Why supernode, not pure mesh

A pure mesh with gossip / DHT is overkill for 4 peers on 3 clouds and would
eat the semester. The supernode pattern is exactly what past projects #13
(Air Quality) and #6 (Surroundings Sensing — MQTT-as-P2P) shipped, and it
gives the overlay its real value: **dynamic capability-based routing between
independently deployed peers**.

Trade-off: the registry is a single point of discovery failure. Peers
already cache their last-known peer set for the lifetime of a request, and
the ledger is replicated through persistent storage. For a production
evolution, the supernode would be replaced by 3 redundant registries with
log-replicated state (Raft-style).
