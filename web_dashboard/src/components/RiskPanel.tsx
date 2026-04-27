import { useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardBody, CardHeader } from "./ui/Card";
import { Stat } from "./ui/Stat";
import type { Portfolio, RiskSnapshot } from "../types";
import { api } from "../api";
import { Calculator, PieChart, Zap } from "lucide-react";

function pct(n: number | undefined) {
  if (n === undefined || Number.isNaN(n)) return "—";
  return `${(n * 100).toFixed(2)}%`;
}

export function RiskPanel({
  portfolio,
  latest,
  history,
  onRecomputed,
}: {
  portfolio: Portfolio | null;
  latest: RiskSnapshot | null;
  history: RiskSnapshot[];
  onRecomputed: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const chartData = useMemo(() => {
    return history.slice(-80).map((s) => ({
      t: new Date(s.as_of).toLocaleTimeString([], { hour12: false }),
      volatility: +(s.volatility * 100).toFixed(4),
      var95: +(s.value_at_risk_95 * 100).toFixed(4),
      drawdown: +(s.max_drawdown * 100).toFixed(4),
      rolling: +(s.rolling_return_1d * 100).toFixed(4),
    }));
  }, [history]);

  async function recompute() {
    setBusy(true);
    setError(null);
    try {
      await api.recomputeRisk();
      onRecomputed();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  }

  async function seed() {
    setBusy(true);
    setError(null);
    try {
      await api.setPortfolio({
        portfolio_id: "demo_portfolio",
        positions: [
          { symbol: "BTCUSD", weight: 0.4 },
          { symbol: "ETHUSD", weight: 0.3 },
          { symbol: "AAPL", weight: 0.2 },
          { symbol: "MSFT", weight: 0.1 },
        ],
      });
      await api.recomputeRisk();
      onRecomputed();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat
          label="Annualized vol (σ̂·√252)"
          value={pct(latest?.volatility)}
          tone="sky"
          icon={Zap}
          sub="dispersion of portfolio returns"
        />
        <Stat
          label="VaR 95% (historical)"
          value={pct(latest?.value_at_risk_95)}
          tone={(latest?.value_at_risk_95 ?? 0) < -0.05 ? "rose" : "amber"}
          icon={Calculator}
          sub="5th-percentile of observed returns"
        />
        <Stat
          label="Max drawdown"
          value={pct(latest?.max_drawdown)}
          tone={(latest?.max_drawdown ?? 0) < -0.1 ? "rose" : "amber"}
          icon={PieChart}
          sub="peak-to-trough equity curve loss"
        />
        <Stat
          label="Rolling 1-day return"
          value={pct(latest?.rolling_return_1d)}
          tone={(latest?.rolling_return_1d ?? 0) >= 0 ? "emerald" : "rose"}
          icon={Zap}
          sub="compounded last-24-obs return"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader
            title="Risk metrics history"
            subtitle={`${history.length} snapshots · shown as %`}
            right={
              <div className="flex gap-2">
                {!portfolio ? (
                  <button
                    onClick={seed}
                    disabled={busy}
                    className="rounded-md border border-ink-700/70 bg-ink-800/60 px-3 py-1 text-xs text-ink-100 hover:border-accent-emerald/40 hover:text-accent-emerald disabled:opacity-50"
                  >
                    Seed demo portfolio
                  </button>
                ) : null}
                <button
                  onClick={recompute}
                  disabled={busy}
                  className="rounded-md border border-ink-700/70 bg-ink-800/60 px-3 py-1 text-xs text-ink-100 hover:border-accent-sky/40 hover:text-accent-sky disabled:opacity-50"
                >
                  Recompute now
                </button>
              </div>
            }
          />
          <CardBody>
            {error ? <div className="mb-3 text-xs text-accent-rose">{error}</div> : null}
            {chartData.length === 0 ? (
              <div className="flex h-64 items-center justify-center text-sm text-ink-400">
                No snapshots yet — seed a portfolio and drive some market events.
              </div>
            ) : (
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 6, right: 8, left: -10, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="2 4" stroke="#1A2230" />
                    <XAxis
                      dataKey="t"
                      tick={{ fill: "#5D6B7E", fontSize: 10 }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      tick={{ fill: "#5D6B7E", fontSize: 10 }}
                      axisLine={false}
                      tickLine={false}
                      width={48}
                    />
                    <Tooltip
                      contentStyle={{
                        background: "#0B0F17",
                        border: "1px solid #1A2230",
                        borderRadius: 8,
                        fontSize: 12,
                      }}
                      labelStyle={{ color: "#B8C0CC" }}
                      formatter={(v: number, name: string) => [`${v.toFixed(2)}%`, name]}
                    />
                    <Legend wrapperStyle={{ color: "#B8C0CC" }} />
                    <Line type="monotone" dataKey="volatility" name="Volatility" stroke="#38BDF8" dot={false} strokeWidth={1.8} />
                    <Line type="monotone" dataKey="var95" name="VaR 95%" stroke="#F59E0B" dot={false} strokeWidth={1.8} />
                    <Line type="monotone" dataKey="drawdown" name="Max DD" stroke="#F43F5E" dot={false} strokeWidth={1.8} />
                    <Line type="monotone" dataKey="rolling" name="Rolling 1d" stroke="#10B981" dot={false} strokeWidth={1.8} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Portfolio" subtitle={portfolio?.portfolio_id ?? "no portfolio loaded"} />
          <CardBody>
            {portfolio ? (
              <ul className="space-y-2">
                {portfolio.positions.map((p) => (
                  <li
                    key={p.symbol}
                    className="flex items-center justify-between rounded-md border border-ink-700/60 bg-ink-900/60 px-3 py-2"
                  >
                    <span className="mono text-sm text-ink-100">{p.symbol}</span>
                    <div className="flex flex-1 items-center gap-3 pl-6">
                      <div className="h-1.5 flex-1 rounded-full bg-ink-700">
                        <div
                          className="h-1.5 rounded-full bg-accent-sky"
                          style={{ width: `${Math.min(100, p.weight * 100)}%` }}
                        />
                      </div>
                      <span className="mono text-sm tabular-nums text-ink-200">{(p.weight * 100).toFixed(0)}%</span>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-ink-400">Seed the demo portfolio from the button above to start computing risk.</p>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
