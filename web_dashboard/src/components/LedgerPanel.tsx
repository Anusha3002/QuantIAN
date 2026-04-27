import { formatDistanceToNowStrict } from "date-fns";
import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ShieldCheck, ShieldX } from "lucide-react";
import { Card, CardBody, CardHeader } from "./ui/Card";
import { Badge } from "./ui/Badge";
import type { LedgerBlock, LedgerVerification } from "../types";

const EVENT_TONE: Record<string, "emerald" | "sky" | "amber" | "rose" | "violet" | "slate"> = {
  peer_registered: "sky",
  peer_heartbeat: "slate",
  market_event_ingested: "sky",
  event_routed_to_anomaly: "violet",
  event_routed_to_risk: "violet",
  event_routed_to_compute: "violet",
  anomaly_alert_created: "amber",
  anomaly_alert_reviewed: "emerald",
  risk_snapshot_computed: "emerald",
  routing_failed: "rose",
  ledger_verification_failed: "rose",
};

export function LedgerPanel({
  blocks,
  verification,
}: {
  blocks: LedgerBlock[];
  verification: LedgerVerification | null;
}) {
  const [typeFilter, setTypeFilter] = useState("all");
  const [hideHeartbeats, setHideHeartbeats] = useState(true);

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const b of blocks) c[b.event_type] = (c[b.event_type] ?? 0) + 1;
    return c;
  }, [blocks]);

  const barData = useMemo(() => {
    return Object.entries(counts)
      .filter(([k]) => k !== "peer_heartbeat")
      .map(([k, v]) => ({ event: k, count: v }))
      .sort((a, b) => b.count - a.count);
  }, [counts]);

  const filtered = useMemo(() => {
    return blocks
      .filter((b) => (hideHeartbeats ? b.event_type !== "peer_heartbeat" : true))
      .filter((b) => (typeFilter === "all" ? true : b.event_type === typeFilter))
      .slice(-60)
      .reverse();
  }, [blocks, typeFilter, hideHeartbeats]);

  const valid = verification?.valid ?? true;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader
          title="Ledger integrity"
          subtitle={`${verification?.block_count ?? blocks.length} blocks · hash-chained, auto-verified by the registry`}
          right={
            <span
              className={
                valid
                  ? "chip border-accent-emerald/40 bg-accent-emerald/10 text-accent-emerald"
                  : "chip border-accent-rose/40 bg-accent-rose/10 text-accent-rose"
              }
            >
              {valid ? <ShieldCheck size={13} /> : <ShieldX size={13} />}
              {valid ? "verified" : "FAILED"}
            </span>
          }
        />
        <CardBody>
          <div className="grid gap-4 md:grid-cols-[1fr_360px]">
            <div className="h-56 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={barData} margin={{ top: 4, right: 6, left: -10, bottom: 30 }}>
                  <CartesianGrid strokeDasharray="2 4" stroke="#1A2230" />
                  <XAxis
                    dataKey="event"
                    tick={{ fill: "#8994A3", fontSize: 10 }}
                    axisLine={false}
                    tickLine={false}
                    angle={-30}
                    textAnchor="end"
                    height={50}
                  />
                  <YAxis
                    tick={{ fill: "#5D6B7E", fontSize: 10 }}
                    axisLine={false}
                    tickLine={false}
                    width={40}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "#0B0F17",
                      border: "1px solid #1A2230",
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                  />
                  <Bar dataKey="count" fill="#38BDF8" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="space-y-2 text-sm">
              <StatRow label="total blocks" value={(verification?.block_count ?? blocks.length).toLocaleString()} />
              <StatRow label="peer heartbeats" value={(counts.peer_heartbeat ?? 0).toLocaleString()} muted />
              <StatRow label="market events ingested" value={(counts.market_event_ingested ?? 0).toLocaleString()} />
              <StatRow label="anomaly alerts" value={(counts.anomaly_alert_created ?? 0).toLocaleString()} tone="amber" />
              <StatRow label="risk snapshots" value={(counts.risk_snapshot_computed ?? 0).toLocaleString()} tone="emerald" />
              <StatRow label="routing failures" value={(counts.routing_failed ?? 0).toLocaleString()} tone={(counts.routing_failed ?? 0) > 0 ? "rose" : "emerald"} />
            </div>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="Block timeline"
          subtitle="Most recent 60 blocks — each hash chains to the previous"
          right={
            <div className="flex items-center gap-2">
              <label className="flex items-center gap-1.5 text-xs text-ink-300">
                <input
                  type="checkbox"
                  checked={hideHeartbeats}
                  onChange={(e) => setHideHeartbeats(e.target.checked)}
                />
                hide heartbeats
              </label>
              <select
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
                className="rounded-md border border-ink-700 bg-ink-800 px-2 py-1 text-xs text-ink-200 outline-none"
              >
                <option value="all">all event types</option>
                {Object.keys(counts)
                  .sort()
                  .map((k) => (
                    <option key={k} value={k}>
                      {k} ({counts[k]})
                    </option>
                  ))}
              </select>
            </div>
          }
        />
        <CardBody>
          {filtered.length === 0 ? (
            <div className="text-sm text-ink-400">No blocks match.</div>
          ) : (
            <ol className="space-y-1.5">
              {filtered.map((b) => (
                <li
                  key={b.block_id}
                  className="grid grid-cols-[64px_160px_1fr_auto] items-center gap-3 rounded-md border border-ink-700/50 bg-ink-900/60 px-3 py-2 text-sm"
                >
                  <span className="mono text-xs text-ink-400">#{b.block_id}</span>
                  <Badge tone={EVENT_TONE[b.event_type] ?? "slate"}>{b.event_type}</Badge>
                  <span className="mono truncate text-xs text-ink-300">by {b.actor_node}</span>
                  <span className="text-xs text-ink-400">
                    {formatDistanceToNowStrict(new Date(b.timestamp), { addSuffix: true })}
                  </span>
                </li>
              ))}
            </ol>
          )}
        </CardBody>
      </Card>
    </div>
  );
}

function StatRow({
  label,
  value,
  tone = "ink",
  muted = false,
}: {
  label: string;
  value: string;
  tone?: "ink" | "emerald" | "amber" | "rose";
  muted?: boolean;
}) {
  const toneClass =
    tone === "emerald"
      ? "text-accent-emerald"
      : tone === "amber"
        ? "text-accent-amber"
        : tone === "rose"
          ? "text-accent-rose"
          : "text-ink-100";
  return (
    <div
      className={`flex items-center justify-between rounded-md border border-ink-700/60 bg-ink-900/60 px-3 py-1.5 ${
        muted ? "opacity-60" : ""
      }`}
    >
      <span className="text-xs text-ink-300">{label}</span>
      <span className={`mono text-sm font-semibold tabular-nums ${toneClass}`}>{value}</span>
    </div>
  );
}
