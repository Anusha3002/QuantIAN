import { Activity, AlertTriangle, Cloud, Cpu, Network, ShieldCheck } from "lucide-react";
import { Card, CardBody, CardHeader } from "./ui/Card";
import { PriceChart } from "./PriceChart";
import { Stat } from "./ui/Stat";
import type {
  AnomalyHealth,
  IngestionHealth,
  IotHealth,
  MarketEvent,
  RegistryHealth,
  RiskHealth,
  RiskSnapshot,
} from "../types";

interface Props {
  registry: RegistryHealth | null;
  ingestion: IngestionHealth | null;
  anomaly: AnomalyHealth | null;
  risk: RiskHealth | null;
  iot: IotHealth | null;
  latestRisk: RiskSnapshot | null;
  events: MarketEvent[];
}

function pct(n: number) {
  return `${(n * 100).toFixed(2)}%`;
}

export function OverviewPanel({ registry, ingestion, anomaly, risk, iot, latestRisk, events }: Props) {
  const peersOnline = registry?.peer_counts.online ?? 0;
  const ledgerValid = registry?.ledger_verifier.last_result?.valid ?? true;
  const ledgerBlocks = registry?.ledger_blocks ?? 0;
  const ledgerRuns = registry?.ledger_verifier.runs ?? 0;
  const normalizedEvents = ingestion?.normalized_events ?? 0;
  const alerts = anomaly?.alerts ?? 0;
  const snapshots = risk?.snapshots ?? 0;

  const ingestionFailures = ingestion?.routing_failures ?? 0;
  const iotReceived = iot?.mqtt_received ?? 0;
  const iotForwarded = iot?.forwarded_to_ingestion ?? 0;

  return (
    <div className="space-y-6">
      {/* KPI strip */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Stat
          icon={Network}
          label="Peers online"
          value={peersOnline}
          sub={`${registry?.peer_counts.stale ?? 0} stale · ${registry?.peer_counts.offline ?? 0} offline`}
          tone="emerald"
        />
        <Stat
          icon={Activity}
          label="Normalized events"
          value={normalizedEvents.toLocaleString()}
          sub={ingestion ? `${ingestion.forwarded_events} forwarded` : undefined}
          tone="sky"
        />
        <Stat
          icon={AlertTriangle}
          label="Anomaly alerts"
          value={alerts}
          sub={anomaly?.sklearn_enabled ? "Isolation Forest ON" : "rule-based only"}
          tone="amber"
        />
        <Stat
          icon={Cpu}
          label="Risk snapshots"
          value={snapshots.toLocaleString()}
          sub={latestRisk ? `σ̂ = ${pct(latestRisk.volatility)}` : undefined}
          tone="violet"
        />
        <Stat
          icon={Cloud}
          label="IoT received"
          value={iotReceived}
          sub={`forwarded ${iotForwarded}`}
          tone="sky"
        />
        <Stat
          icon={ShieldCheck}
          label="Ledger"
          value={ledgerBlocks.toLocaleString()}
          sub={ledgerValid ? `✓ verified · ${ledgerRuns} checks` : "✗ verification FAILED"}
          tone={ledgerValid ? "emerald" : "rose"}
        />
      </div>

      {/* Cloud lanes */}
      <Card>
        <CardHeader title="Cloud lanes" subtitle="One service role per cloud provider, discovered via the registry" />
        <CardBody>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            <CloudLane
              cloud="AWS"
              role="Ingestion + IoT bridge"
              healthy={ingestion?.status === "ok" && iot?.status === "ok"}
              lines={[
                `normalized: ${normalizedEvents}`,
                `routing failures: ${ingestionFailures}`,
                `MQTT: ${iot?.broker ?? "—"}`,
              ]}
            />
            <CloudLane
              cloud="Azure"
              role="Anomaly detection (ML)"
              healthy={anomaly?.status === "ok"}
              lines={[
                `alerts: ${alerts}`,
                `symbols tracked: ${anomaly?.tracked_symbols ?? 0}`,
                `storage: ${anomaly?.storage_backend ?? "—"}`,
              ]}
            />
            <CloudLane
              cloud="GCP"
              role="Portfolio risk"
              healthy={risk?.status === "ok"}
              lines={[
                `snapshots: ${snapshots}`,
                `portfolio loaded: ${risk?.portfolio_loaded ? "yes" : "no"}`,
                `symbols tracked: ${risk?.symbols_tracked ?? 0}`,
              ]}
            />
          </div>
        </CardBody>
      </Card>

      {/* Price + Risk snapshot */}
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader title="Live market feed" subtitle="Last ~40 events per symbol, polled from the ingestion peer" />
          <CardBody className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {["BTCUSD", "ETHUSD", "AAPL", "MSFT"].map((sym) => (
              <div key={sym} className="rounded-lg border border-ink-700/60 bg-ink-900/60 p-3">
                <div className="mb-2 flex items-center justify-between text-xs">
                  <span className="mono font-semibold text-ink-100">{sym}</span>
                  <span className="text-ink-400">
                    {(() => {
                      const last = [...events].reverse().find((e) => e.symbol === sym);
                      return last ? last.price.toFixed(2) : "—";
                    })()}
                  </span>
                </div>
                <PriceChart events={events} symbol={sym} />
              </div>
            ))}
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Latest risk snapshot"
            subtitle={latestRisk ? `as of ${new Date(latestRisk.as_of).toLocaleString()}` : "no snapshot yet"}
          />
          <CardBody className="space-y-3">
            {latestRisk ? (
              <>
                <RiskRow label="Annualized volatility" value={pct(latestRisk.volatility)} tone="sky" />
                <RiskRow
                  label="Value at Risk 95%"
                  value={pct(latestRisk.value_at_risk_95)}
                  tone={latestRisk.value_at_risk_95 < -0.05 ? "rose" : "amber"}
                />
                <RiskRow
                  label="Max drawdown"
                  value={pct(latestRisk.max_drawdown)}
                  tone={latestRisk.max_drawdown < -0.1 ? "rose" : "amber"}
                />
                <RiskRow
                  label="Rolling 1d return"
                  value={pct(latestRisk.rolling_return_1d)}
                  tone={latestRisk.rolling_return_1d >= 0 ? "emerald" : "rose"}
                />
              </>
            ) : (
              <p className="text-sm text-ink-400">Seed a portfolio and run a market cycle to produce a snapshot.</p>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

function CloudLane({
  cloud,
  role,
  healthy,
  lines,
}: {
  cloud: string;
  role: string;
  healthy: boolean;
  lines: string[];
}) {
  const accent =
    cloud === "AWS" ? "text-accent-amber" : cloud === "Azure" ? "text-accent-sky" : "text-accent-emerald";
  return (
    <div className="rounded-lg border border-ink-700/60 bg-ink-900/60 p-4">
      <div className="flex items-center justify-between">
        <div className={`mono text-sm font-semibold ${accent}`}>{cloud}</div>
        <span
          className={`chip ${
            healthy
              ? "border-accent-emerald/40 bg-accent-emerald/10 text-accent-emerald"
              : "border-accent-rose/40 bg-accent-rose/10 text-accent-rose"
          }`}
        >
          {healthy ? "healthy" : "degraded"}
        </span>
      </div>
      <div className="mt-1 text-xs text-ink-300">{role}</div>
      <ul className="mt-3 space-y-1 text-xs text-ink-400">
        {lines.map((line) => (
          <li key={line} className="mono">
            {line}
          </li>
        ))}
      </ul>
    </div>
  );
}

function RiskRow({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: "emerald" | "amber" | "rose" | "sky";
}) {
  const toneClass =
    tone === "emerald"
      ? "text-accent-emerald"
      : tone === "rose"
        ? "text-accent-rose"
        : tone === "sky"
          ? "text-accent-sky"
          : "text-accent-amber";
  return (
    <div className="flex items-center justify-between rounded-md border border-ink-700/60 bg-ink-900/60 px-3 py-2">
      <span className="text-xs text-ink-300">{label}</span>
      <span className={`mono text-sm font-semibold tabular-nums ${toneClass}`}>{value}</span>
    </div>
  );
}
