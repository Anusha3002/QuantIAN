import { useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Cpu,
  LayoutDashboard,
  Network,
  Radio,
  ShieldCheck,
} from "lucide-react";
import { api } from "./api";
import { usePolling } from "./hooks/usePolling";
import { Header } from "./components/Header";
import { OverviewPanel } from "./components/OverviewPanel";
import { PeersPanel } from "./components/PeersPanel";
import { AlertsPanel } from "./components/AlertsPanel";
import { RiskPanel } from "./components/RiskPanel";
import { LedgerPanel } from "./components/LedgerPanel";
import { IoTPanel } from "./components/IoTPanel";

type Tab = "overview" | "peers" | "alerts" | "risk" | "ledger" | "iot";

const TABS: { id: Tab; label: string; icon: typeof LayoutDashboard }[] = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "peers", label: "Peers", icon: Network },
  { id: "alerts", label: "Alerts", icon: AlertTriangle },
  { id: "risk", label: "Risk", icon: Cpu },
  { id: "ledger", label: "Ledger", icon: ShieldCheck },
  { id: "iot", label: "IoT", icon: Radio },
];

export default function App() {
  const [tab, setTab] = useState<Tab>("overview");
  const [refreshSeconds, setRefreshSeconds] = useState<number>(5);
  const intervalMs = refreshSeconds * 1000;

  const registry = usePolling(api.registryHealth, intervalMs);
  const ingestion = usePolling(api.ingestionHealth, intervalMs);
  const anomaly = usePolling(api.anomalyHealth, intervalMs);
  const risk = usePolling(api.riskHealth, intervalMs);
  const iot = usePolling(api.iotHealth, intervalMs);

  const peers = usePolling(api.peers, intervalMs);
  const events = usePolling(() => api.recentEvents(80), intervalMs);
  const alerts = usePolling(api.alerts, intervalMs);
  const portfolio = usePolling(api.portfolio, intervalMs * 2);
  const latestRisk = usePolling(api.latestRisk, intervalMs);
  const riskHistory = usePolling(api.riskHistory, intervalMs * 2);
  const ledgerVerify = usePolling(api.ledgerVerify, intervalMs * 2);
  const ledgerBlocks = usePolling(api.ledgerBlocks, intervalMs * 2);

  const refreshAll = () => {
    registry.refresh();
    ingestion.refresh();
    anomaly.refresh();
    risk.refresh();
    iot.refresh();
    peers.refresh();
    events.refresh();
    alerts.refresh();
    portfolio.refresh();
    latestRisk.refresh();
    riskHistory.refresh();
    ledgerVerify.refresh();
    ledgerBlocks.refresh();
  };

  const { liveLabel, liveTone } = useMemo(() => {
    const errors = [
      registry.error,
      ingestion.error,
      anomaly.error,
      risk.error,
      iot.error,
    ].filter(Boolean);
    const peersOnline = registry.data?.peer_counts.online ?? 0;
    if (errors.length >= 4) return { liveLabel: "All services unreachable", liveTone: "rose" as const };
    if (errors.length > 0) return { liveLabel: `${5 - errors.length}/5 services up`, liveTone: "amber" as const };
    return {
      liveLabel: `live · ${peersOnline} peers online · every ${refreshSeconds}s`,
      liveTone: "emerald" as const,
    };
  }, [registry, ingestion, anomaly, risk, iot, refreshSeconds]);

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.06),transparent_60%),radial-gradient(circle_at_bottom_right,rgba(167,139,250,0.05),transparent_50%)]">
      <Header
        liveLabel={liveLabel}
        liveTone={liveTone}
        refreshSeconds={refreshSeconds}
        onRefreshSecondsChange={setRefreshSeconds}
        onRefreshNow={refreshAll}
      />

      <nav className="sticky top-[57px] z-10 border-b border-ink-700/60 bg-ink-950/85 backdrop-blur">
        <div className="mx-auto flex max-w-[1400px] items-center gap-1 overflow-x-auto px-4 py-2">
          {TABS.map(({ id, label, icon: Icon }) => {
            const active = tab === id;
            return (
              <button
                key={id}
                onClick={() => setTab(id)}
                className={
                  "flex shrink-0 items-center gap-2 rounded-full border px-3.5 py-1.5 text-xs font-medium transition-colors " +
                  (active
                    ? "border-accent-sky/40 bg-accent-sky/10 text-accent-sky"
                    : "border-transparent text-ink-300 hover:border-ink-700/70 hover:bg-ink-800/50 hover:text-ink-100")
                }
              >
                <Icon size={14} />
                {label}
              </button>
            );
          })}
          <div className="flex-1" />
          <span className="hidden items-center gap-2 text-[11px] text-ink-400 md:flex">
            <Activity size={12} />
            {registry.lastUpdated
              ? `registry · ${registry.lastUpdated.toLocaleTimeString([], { hour12: false })}`
              : "…"}
          </span>
        </div>
      </nav>

      <main className="mx-auto max-w-[1400px] px-6 py-6">
        {tab === "overview" ? (
          <OverviewPanel
            registry={registry.data}
            ingestion={ingestion.data}
            anomaly={anomaly.data}
            risk={risk.data}
            iot={iot.data}
            latestRisk={latestRisk.data ?? null}
            events={events.data ?? []}
          />
        ) : null}

        {tab === "peers" ? <PeersPanel peers={peers.data ?? []} /> : null}

        {tab === "alerts" ? (
          <AlertsPanel
            alerts={alerts.data ?? []}
            onReviewed={() => {
              alerts.refresh();
              anomaly.refresh();
            }}
          />
        ) : null}

        {tab === "risk" ? (
          <RiskPanel
            portfolio={portfolio.data}
            latest={latestRisk.data ?? null}
            history={riskHistory.data ?? []}
            onRecomputed={() => {
              latestRisk.refresh();
              riskHistory.refresh();
              risk.refresh();
            }}
          />
        ) : null}

        {tab === "ledger" ? (
          <LedgerPanel
            blocks={ledgerBlocks.data ?? []}
            verification={ledgerVerify.data ?? null}
          />
        ) : null}

        {tab === "iot" ? <IoTPanel iot={iot.data} /> : null}
      </main>

      <footer className="mx-auto max-w-[1400px] px-6 pb-6 pt-2 text-[11px] text-ink-500">
        QuantIAN · peers discovered via shared registry · ledger hash-chained &amp; auto-verified · dashboard served by
        Vite on <span className="mono">localhost:5174</span>
      </footer>
    </div>
  );
}
