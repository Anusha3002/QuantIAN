import type {
  AnomalyAlert,
  AnomalyHealth,
  IngestionHealth,
  IotHealth,
  LedgerBlock,
  LedgerVerification,
  MarketEvent,
  PeerRegistration,
  Portfolio,
  RegistryHealth,
  RiskHealth,
  RiskSnapshot,
} from "./types";

// All service calls go through the Vite dev proxy: /api/<service>/<path>
// so we never hit CORS during development.

const serviceBase = {
  registry: "/api/registry",
  ingestion: "/api/ingestion",
  anomaly: "/api/anomaly",
  risk: "/api/risk",
  iot: "/api/iot",
} as const;

type ServiceKey = keyof typeof serviceBase;

async function request<T>(service: ServiceKey, path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${serviceBase[service]}${path}`, {
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    ...init,
  });
  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(`${service} ${path} → ${response.status}: ${text.slice(0, 140)}`);
  }
  if (response.status === 204 || response.headers.get("content-length") === "0") {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const api = {
  // health
  registryHealth: () => request<RegistryHealth>("registry", "/health"),
  ingestionHealth: () => request<IngestionHealth>("ingestion", "/health"),
  anomalyHealth: () => request<AnomalyHealth>("anomaly", "/health"),
  riskHealth: () => request<RiskHealth>("risk", "/health"),
  iotHealth: () => request<IotHealth>("iot", "/health"),

  // registry + ledger
  peers: () => request<PeerRegistration[]>("registry", "/registry/peers"),
  ledgerVerify: () => request<LedgerVerification>("registry", "/ledger/verify"),
  ledgerBlocks: () => request<LedgerBlock[]>("registry", "/ledger/blocks"),

  // ingestion
  recentEvents: (limit = 40) =>
    request<MarketEvent[]>("ingestion", `/ingestion/events/recent?limit=${limit}`),
  sendSensorMessage: (payload: {
    sensor_id: string;
    symbol: string;
    asset_class: string;
    price: number;
    volume: number;
    source: string;
  }) =>
    request<MarketEvent>("ingestion", "/ingestion/messages", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // anomaly
  alerts: () => request<AnomalyAlert[]>("anomaly", "/anomaly/alerts"),
  reviewAlert: (alertId: string, status: "confirmed" | "false_positive" | "dismissed", notes?: string) =>
    request<AnomalyAlert>("anomaly", `/anomaly/alerts/${alertId}/review`, {
      method: "POST",
      body: JSON.stringify({ reviewer: "web-dashboard", status, notes: notes ?? null }),
    }),

  // risk
  portfolio: () => request<Portfolio>("risk", "/risk/portfolio"),
  latestRisk: () => request<RiskSnapshot | null>("risk", "/risk/latest"),
  riskHistory: () => request<RiskSnapshot[]>("risk", "/risk/history"),
  recomputeRisk: () => request<RiskSnapshot>("risk", "/risk/compute", { method: "POST" }),
  setPortfolio: (portfolio: Portfolio) =>
    request<Portfolio>("risk", "/risk/portfolio", {
      method: "POST",
      body: JSON.stringify(portfolio),
    }),
};

export type QuantianApi = typeof api;
