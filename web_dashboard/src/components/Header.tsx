import { Activity, RefreshCw } from "lucide-react";
import { StatusDot } from "./ui/Badge";

interface Props {
  liveLabel: string;
  liveTone: "emerald" | "amber" | "rose";
  refreshSeconds: number;
  onRefreshSecondsChange: (value: number) => void;
  onRefreshNow: () => void;
}

const refreshOptions = [2, 5, 10, 30, 60];

export function Header({
  liveLabel,
  liveTone,
  refreshSeconds,
  onRefreshSecondsChange,
  onRefreshNow,
}: Props) {
  return (
    <header className="sticky top-0 z-20 border-b border-ink-700/70 bg-ink-950/85 backdrop-blur">
      <div className="mx-auto flex max-w-[1400px] items-center gap-4 px-6 py-3">
        <div className="flex items-center gap-3">
          <div className="grid h-9 w-9 place-items-center rounded-xl border border-ink-700/70 bg-ink-800 text-accent-sky">
            <Activity size={18} />
          </div>
          <div>
            <div className="text-sm font-semibold tracking-wide text-ink-100">
              QuantIAN <span className="text-ink-400">· Ops Console</span>
            </div>
            <div className="text-[11px] uppercase tracking-wider text-ink-400">
              Multi-cloud analytics overlay · AWS · Azure · GCP
            </div>
          </div>
        </div>

        <div className="flex-1" />

        <div className="flex items-center gap-2 rounded-full border border-ink-700/70 bg-ink-800/60 px-3 py-1.5 text-xs">
          <StatusDot tone={liveTone} pulse={liveTone === "emerald"} />
          <span className="text-ink-200">{liveLabel}</span>
        </div>

        <div className="hidden items-center gap-2 rounded-full border border-ink-700/70 bg-ink-800/60 px-3 py-1.5 text-xs text-ink-300 sm:flex">
          <span className="text-ink-400">Refresh</span>
          <select
            className="bg-transparent text-ink-100 outline-none"
            value={refreshSeconds}
            onChange={(e) => onRefreshSecondsChange(Number(e.target.value))}
          >
            {refreshOptions.map((v) => (
              <option key={v} value={v} className="bg-ink-800">
                {v}s
              </option>
            ))}
          </select>
        </div>

        <button
          onClick={onRefreshNow}
          className="group flex items-center gap-1.5 rounded-full border border-ink-700/70 bg-ink-800/60 px-3 py-1.5 text-xs text-ink-200 hover:border-accent-sky/40 hover:text-accent-sky"
        >
          <RefreshCw size={14} className="group-hover:-rotate-12 transition-transform" />
          Refresh now
        </button>
      </div>
    </header>
  );
}
