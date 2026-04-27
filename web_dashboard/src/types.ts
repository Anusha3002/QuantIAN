export type PeerStatus = "online" | "stale" | "offline";

export interface PeerRegistration {
  node_id: string;
  node_type: string;
  cloud: "aws" | "azure" | "gcp" | "local" | "shared";
  base_url: string;
  capabilities: string[];
  status: PeerStatus;
  last_heartbeat: string;
  metadata: Record<string, unknown>;
}

export interface MarketEvent {
  event_id: string;
  symbol: string;
  asset_class: string;
  price: number;
  volume: number;
  source: string;
  ingested_at: string;
  window: {
    price_change_1m?: number;
    volume_change_1m?: number;
    notional_value?: number;
  };
}

export interface AnomalyAlert {
  alert_id: string;
  event_id: string;
  symbol: string;
  severity: "low" | "medium" | "high" | "critical";
  score: number;
  reason: string;
  status: "pending_review" | "confirmed" | "false_positive" | "dismissed";
  created_at: string;
}

export interface Portfolio {
  portfolio_id: string;
  positions: Array<{ symbol: string; weight: number }>;
}

export interface RiskSnapshot {
  snapshot_id: string;
  portfolio_id: string;
  as_of: string;
  volatility: number;
  value_at_risk_95: number;
  max_drawdown: number;
  rolling_return_1d: number;
}

export interface LedgerBlock {
  block_id: number;
  timestamp: string;
  event_type: string;
  actor_node: string;
  payload_hash: string;
  previous_hash: string | null;
  block_hash: string;
}

export interface LedgerVerification {
  valid: boolean;
  block_count: number;
  error: string | null;
}

export interface RegistryHealth {
  status: string;
  service: string;
  peers: number;
  ledger_blocks: number;
  peer_counts: Record<PeerStatus, number>;
  ledger_verifier: {
    interval_seconds: number;
    runs: number;
    failures: number;
    last_checked_at: string | null;
    last_result: LedgerVerification | null;
  };
}

export interface IngestionHealth {
  status: string;
  service: string;
  node_id: string;
  raw_messages: number;
  normalized_events: number;
  forwarded_events: number;
  routing_failures: number;
  base_url: string;
}

export interface AnomalyHealth {
  status: string;
  service: string;
  node_id: string;
  alerts: number;
  tracked_symbols: number;
  sklearn_enabled: boolean;
  storage_backend: string;
  base_url: string;
}

export interface RiskHealth {
  status: string;
  service: string;
  node_id: string;
  symbols_tracked: number;
  portfolio_loaded: boolean;
  snapshots: number;
  base_url: string;
}

export interface IotHealth {
  status: string;
  service: string;
  node_id: string;
  broker: string;
  topics: string[];
  ingestion_url: string;
  mqtt_received: number;
  mqtt_handled: number;
  mqtt_errors: number;
  forwarded_to_ingestion: number;
  forward_failures: number;
  validation_failures: number;
}
