from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from simulator.mqtt_publisher.generator import MarketSensorSimulator


def _run_stdout(args: argparse.Namespace) -> None:
    simulator = MarketSensorSimulator(seed=args.seed)
    for cycle in range(args.cycles):
        anomaly_symbol = args.anomaly_symbol if cycle == max(1, args.cycles // 2) else None
        for message in simulator.generate_cycle(anomaly_symbol=anomaly_symbol):
            print(json.dumps(message.model_dump()))
        if args.delay:
            time.sleep(args.delay)


def _run_mqtt(args: argparse.Namespace) -> None:
    from iot.mqtt_client import parse_broker_url
    from simulator.mqtt_publisher.publisher import SimulatedMarketPublisher

    config = parse_broker_url(args.broker_url)
    publisher = SimulatedMarketPublisher(
        mqtt_config=config,
        simulator=MarketSensorSimulator(seed=args.seed),
    )
    published = publisher.run(
        cycles=args.cycles,
        interval_seconds=args.delay,
        anomaly_cycle=max(1, args.cycles // 2),
        anomaly_symbol=args.anomaly_symbol,
    )
    print(json.dumps({"published": published, "broker": args.broker_url}))


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate QuantIAN market sensor messages.")
    parser.add_argument("--cycles", type=int, default=3)
    parser.add_argument("--delay", type=float, default=0.0)
    parser.add_argument("--anomaly-symbol", default="BTCUSD")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--mqtt",
        action="store_true",
        help="Publish over MQTT instead of stdout.",
    )
    parser.add_argument("--broker-url", default="mqtt://localhost:1883")
    args = parser.parse_args()

    if args.mqtt:
        _run_mqtt(args)
    else:
        _run_stdout(args)


if __name__ == "__main__":
    main()
