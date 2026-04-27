import clsx from "clsx";
import type { ReactNode } from "react";

type Tone = "emerald" | "amber" | "rose" | "sky" | "violet" | "slate";

const tones: Record<Tone, string> = {
  emerald: "border-accent-emerald/40 bg-accent-emerald/10 text-accent-emerald",
  amber: "border-accent-amber/40 bg-accent-amber/10 text-accent-amber",
  rose: "border-accent-rose/40 bg-accent-rose/10 text-accent-rose",
  sky: "border-accent-sky/40 bg-accent-sky/10 text-accent-sky",
  violet: "border-accent-violet/40 bg-accent-violet/10 text-accent-violet",
  slate: "border-ink-600 bg-ink-800 text-ink-200",
};

export function Badge({ tone = "slate", children }: { tone?: Tone; children: ReactNode }) {
  return <span className={clsx("chip", tones[tone])}>{children}</span>;
}

export function StatusDot({ tone = "emerald", pulse = false }: { tone?: Tone; pulse?: boolean }) {
  const color =
    tone === "emerald"
      ? "bg-accent-emerald"
      : tone === "amber"
        ? "bg-accent-amber"
        : tone === "rose"
          ? "bg-accent-rose"
          : tone === "sky"
            ? "bg-accent-sky"
            : tone === "violet"
              ? "bg-accent-violet"
              : "bg-ink-400";
  return (
    <span
      aria-hidden
      className={clsx(
        "inline-block h-2 w-2 rounded-full",
        color,
        pulse && "animate-pulseDot",
      )}
    />
  );
}
