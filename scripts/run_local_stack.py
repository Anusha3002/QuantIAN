from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
VENV_BIN = REPO_ROOT / ".venv" / "bin"
PYTHON = VENV_BIN / "python"
STREAMLIT = VENV_BIN / "streamlit"

DEFAULT_PORTFOLIO = {
    "portfolio_id": "demo_portfolio",
    "positions": [
        {"symbol": "BTCUSD", "weight": 0.4},
        {"symbol": "ETHUSD", "weight": 0.3},
        {"symbol": "AAPL", "weight": 0.2},
        {"symbol": "MSFT", "weight": 0.1},
    ],
}


def wait_for_health(url: str, timeout_seconds: float = 30.0) -> None:
    deadline = time.time() + timeout_seconds
    last_error = "service did not respond"
    with httpx.Client(timeout=2.0) as client:
        while time.time() < deadline:
            try:
                response = client.get(f"{url}/health")
                if response.status_code == 200:
                    return
                last_error = f"unexpected status {response.status_code}"
            except Exception as exc:  # pragma: no cover
                last_error = str(exc)
            time.sleep(0.5)
    raise RuntimeError(f"health check failed for {url}: {last_error}")


def launch_process(command: list[str], env: dict[str, str]) -> subprocess.Popen[str]:
    return subprocess.Popen(
        command,
        cwd=REPO_ROOT,
        env=env,
        stdout=sys.stdout,
        stderr=sys.stderr,
        text=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local QuantIAN stack.")
    parser.add_argument("--with-dashboard", action="store_true")
    parser.add_argument("--autoplay", action="store_true")
    parser.add_argument("--cycles", type=int, default=12)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--reset-state", action="store_true")
    parser.add_argument(
        "--with-iot-bridge",
        action="store_true",
        help="Launch the MQTT -> ingestion bridge. Requires a reachable broker.",
    )
    parser.add_argument(
        "--mqtt-broker-url",
        default=os.getenv("MQTT_BROKER_URL", "mqtt://localhost:1883"),
    )
    args = parser.parse_args()

    if not PYTHON.exists():
        raise SystemExit("Missing .venv. Create it and install dependencies first.")

    data_dir = REPO_ROOT / "data" / "runtime"
    if args.reset_state and data_dir.exists():
        shutil.rmtree(data_dir)

    base_env = os.environ.copy()
    base_env["PYTHONPATH"] = str(REPO_ROOT)
    base_env["QUANTIAN_DATA_DIR"] = str(data_dir)
    base_env["ENABLE_SERVICE_RUNTIME"] = "true"
    base_env["MQTT_BROKER_URL"] = args.mqtt_broker_url

    services = [
        ("registry_service.main:app", 8000),
        ("aws_ingestion.main:app", 8001),
        ("azure_anomaly.main:app", 8002),
        ("gcp_risk.main:app", 8003),
    ]
    processes: list[subprocess.Popen[str]] = []

    try:
        for module, port in services:
            command = [
                str(PYTHON),
                "-m",
                "uvicorn",
                module,
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ]
            processes.append(launch_process(command, base_env))
            wait_for_health(f"http://127.0.0.1:{port}")

        if args.with_iot_bridge:
            bridge_command = [
                str(PYTHON),
                "-m",
                "uvicorn",
                "iot.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8004",
            ]
            processes.append(launch_process(bridge_command, base_env))
            try:
                wait_for_health("http://127.0.0.1:8004", timeout_seconds=10)
            except RuntimeError as exc:
                print(f"iot bridge not healthy (continuing): {exc}")

        with httpx.Client(timeout=5.0) as client:
            client.post("http://127.0.0.1:8003/risk/portfolio", json=DEFAULT_PORTFOLIO).raise_for_status()

        if args.autoplay:
            play_command = [
                str(PYTHON),
                str(REPO_ROOT / "scripts" / "publish_simulation.py"),
                "--cycles",
                str(args.cycles),
                "--interval",
                str(args.interval),
                "--ingestion-url",
                "http://127.0.0.1:8001",
            ]
            processes.append(launch_process(play_command, base_env))

        if args.with_dashboard:
            dashboard_command = [
                str(STREAMLIT),
                "run",
                "dashboard/app.py",
                "--server.headless",
                "true",
                "--server.port",
                "8501",
            ]
            processes.append(launch_process(dashboard_command, base_env))

        print("QuantIAN local stack is running.")
        print("Registry:   http://127.0.0.1:8000")
        print("Ingestion:  http://127.0.0.1:8001")
        print("Anomaly:    http://127.0.0.1:8002")
        print("Risk:       http://127.0.0.1:8003")
        if args.with_iot_bridge:
            print("IoT Bridge: http://127.0.0.1:8004")
        if args.with_dashboard:
            print("Dashboard:  http://127.0.0.1:8501")

        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.send_signal(signal.SIGTERM)
        for process in reversed(processes):
            if process.poll() is None:
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()


if __name__ == "__main__":
    main()
