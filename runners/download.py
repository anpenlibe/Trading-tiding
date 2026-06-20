#!/usr/bin/env python3
"""Historical OHLCV collection from Zerodha into the interval-aware price_data table.

Fetches candles for ``config.SYMBOLS`` (or ``--symbols``) at a chosen interval and
bulk-inserts the raw bars, stamping each with its interval so multiple intervals
(e.g. 1m intraday + 1d daily) coexist in one DB.

Zerodha caps historical range per request by interval (1m ≈ 60 days), so the
window is split into chunks. Unlike the old per-bar path, this does NOT recompute
indicators per candle — the feature layer computes indicators on demand, and the
``indicators`` table is unused — so a ~1M-row pull stays fast.

Examples:
    python apps/data_collector.py --interval 1m --period 6mo
    python apps/data_collector.py --interval 1d --days 545          # ~18 months daily
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.marketdata.sources import ZerodhaAPI
from src.marketdata.store import DatabaseManager
from src.platform.config import SYMBOLS, DB_PATH

# Map our interval labels → Zerodha interval names and per-request day caps.
# Zerodha limits: minute=60d, 3–30min=100d, day=2000d. We stay just under.
ZERODHA_INTERVAL = {"1m": "minute", "5m": "5minute", "15m": "15minute",
                    "30m": "30minute", "1d": "day"}
MAX_CHUNK_DAYS = {"1m": 58, "5m": 95, "15m": 95, "30m": 95, "1d": 1900}

PERIOD_DAYS = {"1mo": 30, "60d": 60, "6mo": 180, "12mo": 365, "18mo": 545}


def compute_date_range(period: str | None, days: int | None):
    """Return (from_date, to_date); explicit --days wins over --period."""
    to_date = datetime.now()
    span = days if days is not None else PERIOD_DAYS[period]
    return to_date - timedelta(days=span), to_date


def date_chunks(from_date, to_date, max_days):
    """Yield (chunk_from, chunk_to) windows no longer than max_days."""
    cur = from_date
    while cur < to_date:
        nxt = min(cur + timedelta(days=max_days), to_date)
        yield cur, nxt
        cur = nxt


def build_arg_parser():
    p = argparse.ArgumentParser(description="Fetch historical Zerodha candles into price_data.")
    p.add_argument("--days", type=int, help="Past days to fetch (overrides --period)")
    p.add_argument("--period", default="1mo", choices=list(PERIOD_DAYS), help="Preset period if --days absent")
    p.add_argument("--interval", default="1d", choices=list(ZERODHA_INTERVAL), help="Candle interval")
    p.add_argument("--symbols", nargs="+", help="Symbols to fetch (overrides config)")
    return p


def main():
    args = build_arg_parser().parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    zerodha = ZerodhaAPI()
    if not zerodha.is_authenticated:
        logging.error("Zerodha not authenticated — refresh the access token "
                      "(scripts/generate_zerodha_token.py) and retry.")
        return

    db = DatabaseManager(DB_PATH)
    from_date, to_date = compute_date_range(args.period, args.days)
    zint = ZERODHA_INTERVAL[args.interval]
    max_days = MAX_CHUNK_DAYS[args.interval]
    symbols = args.symbols or SYMBOLS

    logging.info("Collecting %s candles for %d symbols: %s → %s (chunks ≤ %dd)",
                 args.interval, len(symbols), from_date.date(), to_date.date(), max_days)

    total_saved = 0
    skipped = []
    for symbol in symbols:
        token = zerodha.tokens.get(symbol)
        if not token:
            skipped.append(symbol)
            logging.warning("Skipping %s: no instrument token", symbol)
            continue

        sym_saved = 0
        for cfrom, cto in date_chunks(from_date, to_date, max_days):
            try:
                hist = zerodha.kite.historical_data(token, cfrom, cto, zint, continuous=False)
            except Exception as exc:
                logging.error("  %s %s→%s: %s", symbol, cfrom.date(), cto.date(), exc)
                continue
            for row in hist:
                row["symbol"] = symbol
            sym_saved += db.save_bars_bulk(hist, interval=args.interval)
            time.sleep(0.4)  # respect Zerodha historical rate limit (~3 req/s)

        total_saved += sym_saved
        logging.info("  %-12s saved %d %s bars", symbol, sym_saved, args.interval)

    db.close()
    logging.info("Done. Saved %d %s bars across %d symbols%s.",
                 total_saved, args.interval, len(symbols) - len(skipped),
                 f" ({len(skipped)} skipped: {', '.join(skipped)})" if skipped else "")


if __name__ == "__main__":
    main()
