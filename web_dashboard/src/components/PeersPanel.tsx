import { formatDistanceToNowStrict } from "date-fns";
import { Card, CardBody, CardHeader } from "./ui/Card";
import { Badge, StatusDot } from "./ui/Badge";
import type { PeerRegistration } from "../types";

const cloudColor: Record<string, "amber" | "sky" | "emerald" | "slate"> = {
  aws: "amber",
  azure: "sky",
  gcp: "emerald",
  local: "slate",
  shared: "slate",
};

const statusTone = (s: string): "emerald" | "amber" | "rose" =>
  s === "online" ? "emerald" : s === "stale" ? "amber" : "rose";

export function PeersPanel({ peers }: { peers: PeerRegistration[] }) {
  return (
    <Card>
      <CardHeader
        title="Peer registry"
        subtitle={`${peers.length} peer${peers.length === 1 ? "" : "s"} registered — resolved by capability, not URL`}
        right={
          <div className="flex items-center gap-2 text-xs text-ink-400">
            <StatusDot tone="emerald" pulse /> online
            <StatusDot tone="amber" /> stale
            <StatusDot tone="rose" /> offline
          </div>
        }
      />
      <CardBody className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead>
            <tr className="text-[11px] uppercase tracking-wider text-ink-400">
              <th className="pb-3 pr-4 font-medium">Node</th>
              <th className="pb-3 pr-4 font-medium">Cloud</th>
              <th className="pb-3 pr-4 font-medium">Type</th>
              <th className="pb-3 pr-4 font-medium">Status</th>
              <th className="pb-3 pr-4 font-medium">Capabilities</th>
              <th className="pb-3 pr-4 font-medium">Heartbeat</th>
            </tr>
          </thead>
          <tbody>
            {peers.map((p) => {
              const ageSeconds = (Date.now() - new Date(p.last_heartbeat).getTime()) / 1000;
              return (
                <tr
                  key={p.node_id}
                  className="border-t border-ink-700/50 align-top hover:bg-ink-800/40"
                >
                  <td className="py-3 pr-4">
                    <div className="mono text-ink-100">{p.node_id}</div>
                    <div className="mono text-[11px] text-ink-400">{p.base_url}</div>
                  </td>
                  <td className="py-3 pr-4">
                    <Badge tone={cloudColor[p.cloud] ?? "slate"}>{p.cloud}</Badge>
                  </td>
                  <td className="py-3 pr-4 text-ink-200">{p.node_type}</td>
                  <td className="py-3 pr-4">
                    <div className="flex items-center gap-2">
                      <StatusDot tone={statusTone(p.status)} pulse={p.status === "online"} />
                      <span className="text-ink-100">{p.status}</span>
                    </div>
                  </td>
                  <td className="py-3 pr-4">
                    <div className="flex flex-wrap gap-1.5">
                      {p.capabilities.map((c) => (
                        <span
                          key={c}
                          className="rounded-md border border-ink-700 bg-ink-800 px-1.5 py-0.5 text-[11px] text-ink-200"
                        >
                          {c}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="py-3 pr-4">
                    <span
                      className={
                        ageSeconds > 90
                          ? "text-accent-amber"
                          : ageSeconds > 180
                            ? "text-accent-rose"
                            : "text-ink-200"
                      }
                    >
                      {formatDistanceToNowStrict(new Date(p.last_heartbeat), { addSuffix: true })}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </CardBody>
    </Card>
  );
}
