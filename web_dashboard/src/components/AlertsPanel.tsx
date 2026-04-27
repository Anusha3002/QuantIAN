import { formatDistanceToNowStrict } from "date-fns";
import { useMemo, useState } from "react";
import { Card, CardBody, CardHeader } from "./ui/Card";
import { Badge } from "./ui/Badge";
import type { AnomalyAlert } from "../types";
import { api } from "../api";
import { AlertTriangle, CheckCircle2, Flag, XCircle } from "lucide-react";

const severityTone: Record<AnomalyAlert["severity"], "emerald" | "amber" | "rose" | "violet"> = {
  low: "emerald",
  medium: "amber",
  high: "rose",
  critical: "violet",
};

const statusTone: Record<AnomalyAlert["status"], "slate" | "emerald" | "rose" | "amber"> = {
  pending_review: "amber",
  confirmed: "emerald",
  false_positive: "slate",
  dismissed: "rose",
};

export function AlertsPanel({
  alerts,
  onReviewed,
}: {
  alerts: AnomalyAlert[];
  onReviewed: () => void;
}) {
  const [severityFilter, setSeverityFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const filtered = useMemo(() => {
    return alerts
      .filter((a) => (severityFilter === "all" ? true : a.severity === severityFilter))
      .filter((a) => (statusFilter === "all" ? true : a.status === statusFilter))
      .slice()
      .reverse();
  }, [alerts, severityFilter, statusFilter]);

  const counts = useMemo(() => {
    const c: Record<string, number> = { critical: 0, high: 0, medium: 0, low: 0, pending_review: 0 };
    for (const a of alerts) {
      c[a.severity] = (c[a.severity] ?? 0) + 1;
      c[a.status] = (c[a.status] ?? 0) + 1;
    }
    return c;
  }, [alerts]);

  async function review(alert: AnomalyAlert, status: "confirmed" | "false_positive" | "dismissed") {
    setBusyId(alert.alert_id);
    setErrors((e) => ({ ...e, [alert.alert_id]: "" }));
    try {
      await api.reviewAlert(alert.alert_id, status);
      onReviewed();
    } catch (exc) {
      setErrors((e) => ({ ...e, [alert.alert_id]: exc instanceof Error ? exc.message : String(exc) }));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Card>
      <CardHeader
        title="Anomaly alerts"
        subtitle={`${alerts.length} total · ${counts.pending_review ?? 0} pending review`}
        right={
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="rounded-md border border-ink-700 bg-ink-800 px-2 py-1 text-ink-200 outline-none"
            >
              <option value="all">all severities</option>
              <option value="critical">critical ({counts.critical ?? 0})</option>
              <option value="high">high ({counts.high ?? 0})</option>
              <option value="medium">medium ({counts.medium ?? 0})</option>
              <option value="low">low ({counts.low ?? 0})</option>
            </select>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-md border border-ink-700 bg-ink-800 px-2 py-1 text-ink-200 outline-none"
            >
              <option value="all">all statuses</option>
              <option value="pending_review">pending</option>
              <option value="confirmed">confirmed</option>
              <option value="false_positive">false positive</option>
              <option value="dismissed">dismissed</option>
            </select>
          </div>
        }
      />
      <CardBody>
        {filtered.length === 0 ? (
          <div className="flex items-center gap-3 rounded-lg border border-dashed border-ink-700/60 p-6 text-sm text-ink-400">
            <AlertTriangle className="text-accent-amber" size={18} />
            No alerts match these filters.
          </div>
        ) : (
          <ul className="space-y-2">
            {filtered.map((a) => (
              <li
                key={a.alert_id}
                className="rounded-lg border border-ink-700/60 bg-ink-900/60 p-3 hover:border-ink-600/80"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone={severityTone[a.severity]}>{a.severity}</Badge>
                      <Badge tone={statusTone[a.status]}>{a.status.replace("_", " ")}</Badge>
                      <span className="mono text-sm text-ink-100">{a.symbol}</span>
                      <span className="mono text-xs text-ink-400">
                        score {a.score.toFixed(2)}
                      </span>
                      <span className="text-xs text-ink-400">
                        {formatDistanceToNowStrict(new Date(a.created_at), { addSuffix: true })}
                      </span>
                    </div>
                    <div className="mt-1 text-sm text-ink-200">{a.reason}</div>
                    <div className="mono mt-0.5 text-[11px] text-ink-400">
                      alert: {a.alert_id} · event: {a.event_id}
                    </div>
                    {errors[a.alert_id] ? (
                      <div className="mt-1 text-[11px] text-accent-rose">{errors[a.alert_id]}</div>
                    ) : null}
                  </div>

                  {a.status === "pending_review" ? (
                    <div className="flex shrink-0 gap-2">
                      <ReviewBtn
                        icon={CheckCircle2}
                        label="confirm"
                        tone="emerald"
                        onClick={() => review(a, "confirmed")}
                        busy={busyId === a.alert_id}
                      />
                      <ReviewBtn
                        icon={Flag}
                        label="false+"
                        tone="amber"
                        onClick={() => review(a, "false_positive")}
                        busy={busyId === a.alert_id}
                      />
                      <ReviewBtn
                        icon={XCircle}
                        label="dismiss"
                        tone="rose"
                        onClick={() => review(a, "dismissed")}
                        busy={busyId === a.alert_id}
                      />
                    </div>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}

function ReviewBtn({
  icon: Icon,
  label,
  tone,
  onClick,
  busy,
}: {
  icon: typeof CheckCircle2;
  label: string;
  tone: "emerald" | "amber" | "rose";
  onClick: () => void;
  busy: boolean;
}) {
  const toneClass =
    tone === "emerald"
      ? "hover:border-accent-emerald/40 hover:text-accent-emerald"
      : tone === "amber"
        ? "hover:border-accent-amber/40 hover:text-accent-amber"
        : "hover:border-accent-rose/40 hover:text-accent-rose";
  return (
    <button
      disabled={busy}
      onClick={onClick}
      className={`flex items-center gap-1 rounded-md border border-ink-700/70 bg-ink-800/60 px-2 py-1 text-xs text-ink-200 ${toneClass} disabled:opacity-50`}
    >
      <Icon size={13} />
      {label}
    </button>
  );
}
