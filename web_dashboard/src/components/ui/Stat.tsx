import clsx from "clsx";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

export function Stat({
  label,
  value,
  sub,
  tone = "ink",
  icon: Icon,
  right,
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  tone?: "ink" | "emerald" | "amber" | "rose" | "sky" | "violet";
  icon?: LucideIcon;
  right?: ReactNode;
}) {
  const toneClasses: Record<string, string> = {
    ink: "text-ink-100",
    emerald: "text-accent-emerald",
    amber: "text-accent-amber",
    rose: "text-accent-rose",
    sky: "text-accent-sky",
    violet: "text-accent-violet",
  };
  return (
    <div className="panel flex items-start gap-4 p-4">
      {Icon ? (
        <div className="mt-0.5 rounded-lg border border-ink-700/70 bg-ink-800 p-2 text-ink-200">
          <Icon size={18} />
        </div>
      ) : null}
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-2">
          <span className="text-[11px] font-medium uppercase tracking-wider text-ink-400">{label}</span>
          {right ? <span className="shrink-0 text-[11px] text-ink-400">{right}</span> : null}
        </div>
        <div className={clsx("mt-1 text-2xl font-semibold tabular-nums", toneClasses[tone])}>{value}</div>
        {sub ? <div className="mt-1 text-xs text-ink-400">{sub}</div> : null}
      </div>
    </div>
  );
}
