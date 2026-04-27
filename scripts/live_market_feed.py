#!/usr/bin/env python3
"""
live_market_feed.py — QuantIAN Live Market Data Fetcher
========================================================
Pulls real-time prices from Yahoo Finance and feeds them into the
QuantIAN AWS ingestion endpoint as MarketSensorMessage payloads.

This replaces the MQTT simulator with actual market data so the demo
shows real price movements being routed across clouds in real time.

Usage
-----
  # Default: use the live deployed endpoint
  python scripts/live_market_feed.py

  # Local development stack
  python scripts/live_market_feed.py --endpoint http://localhost:8001

  # Custom interval and symbols
  python scripts/live_market_feed.py --interval 30 --symbols AAPL MSFT BTCUSD

Requirements
------------
  pip install yfinance requests
"""

from __future__ import annotations

import argparse
import datetime
import logging
import sys
import time
from typing import Literal

import requests
import yfinance as yf

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("live_feed")

# ---------------------------------------------------------------------------
# Symbol config  (symbol → asset_class expected by the ingestion schema)
# ---------------------------------------------------------------------------
AssetClass = Literal["equity", "crypto", "forex", "commodity"]

SYMBOL_MAP: dict[str, AssetClass] = {
    # Equities
    "AAPL":  "equity",
    "MSFT":  "equity",
    "NVDA":  "equity",
    "TSLA":  "equity",
    "AMZN":  "equity",
    "GOOGL": "equity",
    # Crypto  (yfinance suffix: -USD)
    "BTC-USD": "crypto",
    "ETH-USD": "crypto",
    # Commodities
    "GC=F":  "commodity",   # Gold futures
    "CL=F":  "commodity",   # Crude oil futures
}

# Display name used as MarketSensorMessage.symbol
# (strips the yfinance ticker quirks for downstream consumers)
DISPLAY_SYMBOL: dict[str, str] = {
    "BTC-USD": "BTCUSD",
    "ETH-USD": "ETHUSD",
    "GC=F":    "GOLD",
    "CL=F":    "OILWTI",
}


# ---------------------------------------------------------------------------
# Fetch helpers
# ---------------------------------------------------------------------------

def fetch_prices(tickers: list[str]) -> dict[str, dict]:
    """
    Download the latest 1-minute bar for each ticker.
    Returns a dict of { yfinance_ticker: {price, volume} }.
    Falls back to the previous close if intraday data is unavailable
    (e.g. weekend / market closed).
    """
    data: dict[str, dict] = {}

    # Batch download — one network round-trip for all tickers
    raw = yf.download(
        tickers=tickers,
        period="1d",
        interval="1m",
        progress=False,
        auto_adjust=True,
        group_by="ticker",
        threads=True,
    )

    for ticker in tickers:
        try:
            if len(tickers) == 1:
                df = raw
            else:
                df = raw[ticker]

            if df.empty:
                log.warning("No data returned for %s — skipping", ticker)
                continue

            last = df.iloc[-1]
            price  = float(last["Close"])
            volume = float(last["Volume"]) if last["Volume"] > 0 else 1_000.0

            data[ticker] = {"price": price, "volume": volume}

        except Exception as exc:
            log.warning("Could not extract price for %s: %s", ticker, exc)

    return data


# ---------------------------------------------------------------------------
# POST to ingestion
# ---------------------------------------------------------------------------

def post_message(endpoint: str, payload: dict, *, timeout: int = 10) -> bool:
    """POST a single MarketSensorMessage to /ingestion/messages."""
    url = f"{endpoint.rstrip('/')}/ingestion/messages"
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        return True
    except requests.exceptions.ConnectionError:
        log.error("Cannot reach ingestion endpoint at %s — is the stack running?", url)
        return False
    except requests.exceptions.HTTPError as exc:
        log.error("HTTP %s from ingestion: %s", exc.response.status_code, exc.response.text[:200])
        return False
    except Exception as exc:
        log.error("Unexpected error posting to ingestion: %s", exc)
        return False


# ---------------------------------------------------------------------------
# One feed cycle
# ---------------------------------------------------------------------------

def run_cycle(tickers: list[str], endpoint: str) -> tuple[int, int]:
    """Fetch prices and post each one. Returns (sent, failed)."""
    log.info("Fetching prices for: %s", ", ".join(tickers))
    prices = fetch_prices(tickers)

    sent = failed = 0
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    for ticker, data in prices.items():
        display   = DISPLAY_SYMBOL.get(ticker, ticker.replace("-", "").replace("=F", ""))
        asset_cls = SYMBOL_MAP.get(ticker, "equity")

        payload = {
            "sensor_id":  f"live-feed-{display.lower()}",
            "symbol":     display,
            "asset_class": asset_cls,
            "price":      round(data["price"], 6),
            "volume":     round(data["volume"], 2),
            "source":     "yahoo-finance-live",
            "event_time": now_iso,
        }

        ok = post_message(endpoint, payload)
        if ok:
            log.info(
                "  ✓ %-8s  $%-12.4f  vol=%.0f  [%s]",
                display, data["price"], data["volume"], asset_cls,
            )
            sent += 1
        else:
            failed += 1

    return sent, failed


# ---------------------------------------------------------------------------
# CLI + main loop
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Feed live Yahoo Finance prices into QuantIAN's ingestion endpoint.",
    )
    parser.add_argument(
        "--endpoint",
        default="http://3.217.147.34:8001",
        help="Base URL of the AWS ingestion service (default: live deployment)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=60.0,
        help="Seconds between fetch cycles (default: 60)",
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=list(SYMBOL_MAP.keys()),
        help="Whitespace-separated list of yfinance tickers to track",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single cycle and exit (useful for testing)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    tickers  = args.symbols
    endpoint = args.endpoint
    interval = args.interval

    log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    log.info("  QuantIAN Live Market Feed")
    log.info("  Endpoint : %s", endpoint)
    log.info("  Symbols  : %s", ", ".join(tickers))
    log.info("  Interval : %ss", interval)
    log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    cycle = 0
    total_sent = total_failed = 0

    while True:
        cycle += 1
        log.info("── Cycle %d ──────────────────────────────────", cycle)
        sent, failed = run_cycle(tickers, endpoint)
        total_sent   += sent
        total_failed += failed
        log.info("  Cycle done: %d sent, %d failed  (total: %d/%d)",
                 sent, failed, total_sent, total_sent + total_failed)

        if args.once:
            break

        log.info("  Next fetch in %gs …", interval)
        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            log.info("Interrupted — exiting. Total sent: %d", total_sent)
            sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Stopped.")
        sys.exit(0)
