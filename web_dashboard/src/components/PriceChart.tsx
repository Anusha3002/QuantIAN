import { useMemo } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { MarketEvent } from "../types";

const SERIES_COLORS: Record<string, string> = {
  BTCUSD: "#F59E0B",
  ETHUSD: "#A78BFA",
  AAPL: "#38BDF8",
  MSFT: "#10B981",
};

interface Props {
  events: MarketEvent[];
  symbol: string;
}

export function PriceChart({ events, symbol }: Props) {
  const data = useMemo(() => {
    return events
      .filter((e) => e.symbol === symbol)
      .slice(-40)
      .map((e) => ({
        t: new Date(e.ingested_at).toLocaleTimeString([], { hour12: false }),
        price: e.price,
      }));
  }, [events, symbol]);

  const color = SERIES_COLORS[symbol] ?? "#38BDF8";
  const gradId = `grad-${symbol}`;

  if (data.length === 0) {
    return (
      <div className="flex h-40 items-center justify-center text-xs text-ink-400">
        no {symbol} events yet
      </div>
    );
  }

  return (
    <div className="h-40 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 4, right: 6, left: -10, bottom: 0 }}>
          <defs>
            <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.5} />
              <stop offset="100%" stopColor={color} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="2 4" stroke="#1A2230" />
          <XAxis dataKey="t" tick={{ fill: "#5D6B7E", fontSize: 10 }} axisLine={false} tickLine={false} />
          <YAxis
            domain={["auto", "auto"]}
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
            formatter={(v: number) => [v.toFixed(2), symbol]}
          />
          <Area
            type="monotone"
            dataKey="price"
            stroke={color}
            strokeWidth={1.6}
            fill={`url(#${gradId})`}
            dot={false}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
