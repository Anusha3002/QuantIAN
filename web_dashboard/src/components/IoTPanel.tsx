import { Radio, Send, Wifi, WifiOff } from "lucide-react";
import { useState } from "react";
import { Card, CardBody, CardHeader } from "./ui/Card";
import { Stat } from "./ui/Stat";
import type { IotHealth } from "../types";
import { api } from "../api";

export function IoTPanel({ iot }: { iot: IotHealth | null }) {
  const reachable = iot !== null;
  const [busy, setBusy] = useState(false);
  const [lastResult, setLastResult] = useState<string | null>(null);

  async function sendOne() {
    setBusy(true);
    setLastResult(null);
    try {
      const result = await api.sendSensorMessage({
        sensor_id: "sensor-manual",
        symbol: "BTCUSD",
        asset_class: "crypto",
        price: 68000 + Math.random() * 200 - 100,
        volume: 120000 + Math.random() * 20000 - 10000,
        source: "web-dashboard",
      });
      setLastResult(`sent ${result.event_id} for ${result.symbol}`);
    } catch (exc) {
      setLastResult(`error: ${exc instanceof Error ? exc.message : String(exc)}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat
          icon={reachable ? Wifi : WifiOff}
          label="Bridge"
          value={reachable ? "online" : "offline"}
          sub={iot?.broker ?? "bridge unreachable"}
          tone={reachable ? "emerald" : "rose"}
        />
        <Stat
          icon={Radio}
          label="MQTT received"
          value={(iot?.mqtt_received ?? 0).toLocaleString()}
          sub={`${iot?.mqtt_handled ?? 0} handled · ${iot?.mqtt_errors ?? 0} parse errors`}
          tone="sky"
        />
        <Stat
          icon={Send}
          label="Forwarded to ingestion"
          value={(iot?.forwarded_to_ingestion ?? 0).toLocaleString()}
          sub={`${iot?.forward_failures ?? 0} failures · ${iot?.validation_failures ?? 0} invalid payloads`}
          tone="violet"
        />
        <Stat
          label="Topic pattern"
          value={iot?.topics.join(", ") ?? "—"}
          sub={`target: ${iot?.ingestion_url ?? "—"}`}
          tone="ink"
        />
      </div>

      <Card>
        <CardHeader
          title="How the IoT layer works"
          subtitle="AWS IoT Core → Lambda pattern, modeled locally with Mosquitto"
        />
        <CardBody>
          <ol className="list-decimal space-y-2 pl-5 text-sm text-ink-300 marker:text-ink-500">
            <li>
              A simulated sensor publishes market ticks to{" "}
              <span className="mono text-accent-sky">quantian/market/&lt;asset_class&gt;/&lt;symbol&gt;</span>{" "}
              on the MQTT broker.
            </li>
            <li>
              The <span className="mono text-ink-100">iot-bridge</span> service (a registered peer in the overlay)
              subscribes to the topic pattern and validates each payload against the{" "}
              <span className="mono text-ink-100">MarketSensorMessage</span> schema.
            </li>
            <li>
              Valid payloads are POSTed to <span className="mono text-ink-100">aws-ingestion</span>, which normalizes
              them and routes to anomaly + risk peers via capability-based discovery.
            </li>
            <li>
              Every stage writes to the append-only hash-chained ledger, so the full chain of custody for each tick is
              auditable.
            </li>
          </ol>
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="Inject a synthetic tick"
          subtitle="Bypasses MQTT, posts directly to the ingestion peer to exercise the same downstream flow"
        />
        <CardBody>
          <div className="flex items-center gap-3">
            <button
              onClick={sendOne}
              disabled={busy}
              className="flex items-center gap-2 rounded-md border border-ink-700/70 bg-ink-800/60 px-3 py-1.5 text-xs text-ink-100 hover:border-accent-sky/40 hover:text-accent-sky disabled:opacity-50"
            >
              <Send size={14} />
              {busy ? "sending…" : "send synthetic BTCUSD tick"}
            </button>
            {lastResult ? (
              <span className="mono text-[11px] text-ink-400">{lastResult}</span>
            ) : null}
          </div>
          <p className="mt-3 text-xs text-ink-400">
            To push via MQTT instead:{" "}
            <span className="mono text-ink-200">
              PYTHONPATH=$PWD .venv/bin/python -m simulator.mqtt_publisher.cli --mqtt --cycles 5 --delay 1
              --broker-url mqtt://localhost:1883
            </span>
          </p>
        </CardBody>
      </Card>
    </div>
  );
}
