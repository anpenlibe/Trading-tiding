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
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.marketdata.sources import ZerodhaAPI
from src.marketdata.store import DatabaseManager
from src.marketdata.backfill import ZERODHA_INTERVAL, download_range
from src.platform.config import SYMBOLS, DB_PATH

PERIOD_DAYS = {"1mo": 30, "60d": 60, "6mo": 180, "12mo": 365, "18mo": 545}


def compute_date_range(period: str | None, days: int | None):
    """Return (from_date, to_date); explicit --days wins over --period."""
    to_date = datetime.now()
    span = days if days is not None else PERIOD_DAYS[period]
    return to_date - timedelta(days=span), to_date


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
    symbols = args.symbols or SYMBOLS

    logging.info("Collecting %s candles for %d symbols: %s → %s",
                 args.interval, len(symbols), from_date.date(), to_date.date())

    total_saved = 0
    skipped = []
    for symbol in symbols:
        if not zerodha.tokens.get(symbol):
            skipped.append(symbol)  # download_range logs the skip
        sym_saved = download_range(zerodha, db, symbol, from_date, to_date, args.interval)
        total_saved += sym_saved
        if symbol not in skipped:
            logging.info("  %-12s saved %d %s bars", symbol, sym_saved, args.interval)

    db.close()
    logging.info("Done. Saved %d %s bars across %d symbols%s.",
                 total_saved, args.interval, len(symbols) - len(skipped),
                 f" ({len(skipped)} skipped: {', '.join(skipped)})" if skipped else "")


if __name__ == "__main__":
    main()
