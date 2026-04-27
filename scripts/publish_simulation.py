from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from simulator.mqtt_publisher import MarketSensorSimulator


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish simulated market traffic to the ingestion service.")
    parser.add_argument("--ingestion-url", default="http://127.0.0.1:8001")
    parser.add_argument("--cycles", type=int, default=12)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--anomaly-cycle", type=int, default=6)
    parser.add_argument("--anomaly-symbol", default="BTCUSD")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    simulator = MarketSensorSimulator(seed=args.seed)
    published = []
    with httpx.Client(timeout=5.0) as client:
        for cycle in range(args.cycles):
            anomaly_symbol = args.anomaly_symbol if cycle == args.anomaly_cycle else None
            messages = simulator.generate_cycle(anomaly_symbol=anomaly_symbol)
            for message in messages:
                response = client.post(f"{args.ingestion_url}/ingestion/messages", json=message.model_dump())
                response.raise_for_status()
                payload = response.json()
                published.append({"cycle": cycle, "symbol": payload["symbol"], "event_id": payload["event_id"]})
            if cycle != args.cycles - 1:
                time.sleep(args.interval)

    print(json.dumps({"published_events": published, "count": len(published)}, indent=2))


if __name__ == "__main__":
    main()
