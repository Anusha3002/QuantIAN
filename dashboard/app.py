from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import streamlit as st

from simulator.mqtt_publisher import MarketSensorSimulator

DEFAULT_PORTFOLIO = {
    "portfolio_id": "demo_portfolio",
    "positions": [
        {"symbol": "BTCUSD", "weight": 0.4},
        {"symbol": "ETHUSD", "weight": 0.3},
        {"symbol": "AAPL", "weight": 0.2},
        {"symbol": "MSFT", "weight": 0.1},
    ],
}


def fetch_json(url: str) -> tuple[object | None, str | None]:
    request = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=5) as response:
            return json.loads(response.read().decode("utf-8")), None
    except HTTPError as exc:
        return None, f"{exc.code} {exc.reason}"
    except URLError as exc:
        return None, str(exc.reason)


def send_json(method: str, url: str, payload: dict[str, Any] | None = None) -> tuple[object | None, str | None]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=data,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urlopen(request, timeout=5) as response:
            body = response.read().decode("utf-8")
            return (json.loads(body) if body else None), None
    except HTTPError as exc:
        message = exc.read().decode("utf-8") or f"{exc.code} {exc.reason}"
        return None, message
    except URLError as exc:
        return None, str(exc.reason)


def render_health_card(label: str, url: str) -> None:
    data, error = fetch_json(f"{url}/health")
    with st.container(border=True):
        st.subheader(label)
        if error:
            st.error(error)
            return
        st.json(data)


REGISTRY_URL = os.getenv("REGISTRY_URL", "http://localhost:8000")
INGESTION_URL = os.getenv("AWS_INGESTION_URL", "http://localhost:8001")
ANOMALY_URL = os.getenv("AZURE_ANOMALY_URL", "http://localhost:8002")
RISK_URL = os.getenv("GCP_RISK_URL", "http://localhost:8003")
IOT_BRIDGE_URL = os.getenv("IOT_BRIDGE_URL", "http://localhost:8004")
SIMULATOR_SEED = int(os.getenv("SIMULATOR_SEED", "42"))

if "simulator" not in st.session_state:
    st.session_state["simulator"] = MarketSensorSimulator(seed=SIMULATOR_SEED)


def send_market_cycle(*, anomaly: bool) -> None:
    simulator: MarketSensorSimulator = st.session_state["simulator"]
    anomaly_symbol = "BTCUSD" if anomaly else None
    results = []
    for message in simulator.generate_cycle(anomaly_symbol=anomaly_symbol):
        response, error = send_json("POST", f"{INGESTION_URL}/ingestion/messages", message.model_dump())
        results.append({"symbol": message.symbol, "error": error, "response": response})
    st.session_state["last_cycle_results"] = results

st.set_page_config(page_title="QuantIAN Dashboard", layout="wide")
st.title("QuantIAN Dashboard")
st.caption("Lightweight local dashboard for the multi-cloud MVP.")

with st.sidebar:
    st.header("Live View")
    auto_refresh = st.toggle("Auto-refresh", value=False, key="auto_refresh")
    refresh_seconds = st.slider(
        "Refresh every (s)",
        min_value=2,
        max_value=30,
        value=5,
        disabled=not auto_refresh,
    )
    if auto_refresh:
        # meta refresh keeps us dependency-free (no streamlit_autorefresh required)
        st.markdown(
            f"<meta http-equiv='refresh' content='{refresh_seconds}'>",
            unsafe_allow_html=True,
        )
    st.caption("Toggle on to watch peers, alerts, risk, and the ledger update live.")

overview_tab, control_tab, peers_tab, alerts_tab, risk_tab, ledger_tab, iot_tab = st.tabs(
    ["Overview", "Controls", "Peers", "Alerts", "Risk", "Ledger", "IoT"]
)

with overview_tab:
    col1, col2 = st.columns(2)
    with col1:
        render_health_card("Registry", REGISTRY_URL)
        render_health_card("AWS Ingestion", INGESTION_URL)
    with col2:
        render_health_card("Azure Anomaly", ANOMALY_URL)
        render_health_card("GCP Risk", RISK_URL)

with control_tab:
    st.subheader("Runtime Controls")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Seed Portfolio", use_container_width=True):
            _, error = send_json("POST", f"{RISK_URL}/risk/portfolio", DEFAULT_PORTFOLIO)
            if error:
                st.error(error)
            else:
                st.success("Portfolio seeded.")
    with col2:
        if st.button("Send Market Cycle", use_container_width=True):
            send_market_cycle(anomaly=False)
    with col3:
        if st.button("Send Anomalous Cycle", use_container_width=True):
            send_market_cycle(anomaly=True)

    if st.button("Recompute Risk", use_container_width=True):
        _, error = send_json("POST", f"{RISK_URL}/risk/compute")
        if error:
            st.error(error)
        else:
            st.success("Risk recomputed.")

    cycle_results = st.session_state.get("last_cycle_results")
    if cycle_results:
        st.dataframe(cycle_results, use_container_width=True)

with peers_tab:
    peers, error = fetch_json(f"{REGISTRY_URL}/registry/peers")
    if error:
        st.error(error)
    else:
        st.dataframe(peers, use_container_width=True)

with alerts_tab:
    alerts, error = fetch_json(f"{ANOMALY_URL}/anomaly/alerts")
    if error:
        st.error(error)
    else:
        st.dataframe(alerts, use_container_width=True)
        alert_ids = [item["alert_id"] for item in alerts]
        if alert_ids:
            selected_alert = st.selectbox("Alert To Review", alert_ids)
            review_status = st.selectbox("Review Status", ["confirmed", "false_positive", "dismissed"])
            review_notes = st.text_input("Review Notes")
            if st.button("Submit Review", use_container_width=True):
                _, review_error = send_json(
                    "POST",
                    f"{ANOMALY_URL}/anomaly/alerts/{selected_alert}/review",
                    {
                        "reviewer": "dashboard-user",
                        "status": review_status,
                        "notes": review_notes or None,
                    },
                )
                if review_error:
                    st.error(review_error)
                else:
                    st.success("Review submitted.")

with risk_tab:
    portfolio, portfolio_error = fetch_json(f"{RISK_URL}/risk/portfolio")
    if portfolio_error:
        st.warning(portfolio_error)
    else:
        st.json(portfolio)

    snapshot, error = fetch_json(f"{RISK_URL}/risk/latest")
    if error:
        st.warning(error)
    else:
        st.json(snapshot)

    history, error = fetch_json(f"{RISK_URL}/risk/history")
    if error:
        st.warning(error)
    elif history:
        st.dataframe(history, use_container_width=True)

with ledger_tab:
    verification, verify_error = fetch_json(f"{REGISTRY_URL}/ledger/verify")
    blocks, blocks_error = fetch_json(f"{REGISTRY_URL}/ledger/blocks")

    col1, col2, col3 = st.columns(3)
    if blocks and not blocks_error:
        col1.metric("Blocks", len(blocks))
        event_counts: dict[str, int] = {}
        for block in blocks:
            event_counts[block["event_type"]] = event_counts.get(block["event_type"], 0) + 1
        col2.metric("Distinct event types", len(event_counts))
        routing_failures = event_counts.get("routing_failed", 0)
        col3.metric("Routing failures", routing_failures, delta_color="inverse")

    if verify_error:
        st.error(verify_error)
    elif verification:
        if verification.get("valid"):
            st.success(f"Ledger verified: {verification.get('block_count')} blocks intact")
        else:
            st.error(f"Ledger verification FAILED: {verification.get('error')}")

    if blocks_error:
        st.error(blocks_error)
    elif blocks:
        st.subheader("Recent blocks")
        recent = blocks[-25:][::-1]
        for block in recent:
            emoji = {
                "peer_registered": "📡",
                "peer_heartbeat": "💓",
                "market_event_ingested": "📥",
                "event_routed_to_anomaly": "➡️",
                "event_routed_to_risk": "➡️",
                "anomaly_alert_created": "🚨",
                "anomaly_alert_reviewed": "✅",
                "risk_snapshot_computed": "📊",
                "routing_failed": "⚠️",
                "ledger_verification_failed": "🔒",
            }.get(block["event_type"], "•")
            st.markdown(
                f"{emoji} **#{block['block_id']}** `{block['event_type']}` "
                f"· {block['actor_node']} · {block['timestamp']}"
            )

        with st.expander("Full ledger (all blocks)"):
            st.dataframe(blocks, use_container_width=True)

with iot_tab:
    st.subheader("IoT Bridge")
    bridge_data, bridge_error = fetch_json(f"{IOT_BRIDGE_URL}/health")
    if bridge_error:
        st.info(
            "IoT bridge not reachable at "
            f"`{IOT_BRIDGE_URL}`. Start it with "
            "`python scripts/run_local_stack.py --with-iot-bridge` and an MQTT broker running."
        )
        st.caption(f"Error: {bridge_error}")
    else:
        col1, col2, col3 = st.columns(3)
        col1.metric("MQTT received", bridge_data.get("mqtt_received", 0))
        col2.metric("Forwarded to ingestion", bridge_data.get("forwarded_to_ingestion", 0))
        col3.metric("Forward failures", bridge_data.get("forward_failures", 0), delta_color="inverse")
        st.json(bridge_data)

    st.divider()
    st.markdown(
        "**How it works:** simulated edge sensors publish to "
        "`quantian/market/<asset_class>/<symbol>` on an MQTT broker. "
        "The IoT bridge subscribes, validates each tick, and POSTs it to the "
        "AWS ingestion peer — mirroring the AWS IoT Core Rule → Lambda pattern."
    )
