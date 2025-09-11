"""
collect_historical_data.py - Unified Historical Data Collection

FIXED ISSUES:
- Now uses config.SYMBOLS instead of hardcoded list  
- Uses DataCollector's unified pipeline for validation and indicators
- Proper encapsulation - no direct database access
- Historical data now gets same validation and indicator processing as live data

Features:
- CLI flags: --period (1mo/60d/6mo), --interval (1m/5m/15m/30m/1d)
- Interactive prompt: if --days not provided, ask user at runtime
- Data stored via DataCollector unified pipeline
- UPSERT handling via database UNIQUE constraints
"""

#!/usr/bin/env python3

import argparse
import logging
import time
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_collector import DataCollector
from src.data.data_sources import ZerodhaAPI, MarketData
from src.data.config import SYMBOLS  # FIXED: Import from config instead of hardcoding

# ──────────────────────────────────────────────────────────────────────────────
#  DEFAULT CONFIGS (overridable via CLI or prompt)
# ──────────────────────────────────────────────────────────────────────────────
DEFAULT_PERIOD = "1mo"       # fallback period if no --days
DEFAULT_INTERVAL = "5m"      # 1m, 5m, 15m, 30m, 1d

INTERVAL_MAP = {
    "1m": "minute",
    "5m": "5minute",
    "15m": "15minute",
    "30m": "30minute",
    "1d": "day",
}

# ──────────────────────────────────────────────────────────────────────────────
#  UTILITIES
# ──────────────────────────────────────────────────────────────────────────────

def compute_date_range(period: str | None = None, days: int | None = None):
    """Return (from_date, to_date) based on either explicit days or a known period."""
    to_date = datetime.now()
    if days is not None:
        return to_date - timedelta(days=days), to_date

    match period:
        case "1mo":  from_date = to_date - timedelta(days=30)
        case "60d":  from_date = to_date - timedelta(days=60)
        case "6mo":  from_date = to_date - timedelta(days=180)
        case _: raise ValueError(f"Unsupported period: {period}")
    return from_date, to_date

# ──────────────────────────────────────────────────────────────────────────────
#  MAIN ENTRYPOINT
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Fetch historical candles and store via DataCollector unified pipeline."
    )
    parser.add_argument(
        "--days", type=int,
        help="Number of past days to fetch (overrides --period)"
    )
    parser.add_argument(
        "--period", default=DEFAULT_PERIOD,
        choices=["1mo", "60d", "6mo"],
        help="Preset period if --days not given"
    )
    parser.add_argument(
        "--interval", default=DEFAULT_INTERVAL,
        choices=list(INTERVAL_MAP.keys()),
        help="Candle interval"
    )
    args = parser.parse_args()

    # Interactive prompt for days if not provided on CLI
    if args.days is None:
        resp = input(f"Enter number of past days to fetch (press Enter to use period={args.period}): ").strip()
        if resp:
            try:
                args.days = int(resp)
            except ValueError:
                print(f"Invalid input '{resp}', proceeding with period={args.period}.")

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    # Initialize collector and API
    collector = DataCollector()
    zerodha = ZerodhaAPI()

    # Compute date range
    from_date, to_date = compute_date_range(
        period=args.period,
        days=args.days
    )
    interval = INTERVAL_MAP[args.interval]

    logging.info(f"Historical data collection started")
    logging.info(f"Symbols: {len(SYMBOLS)} from config")
    logging.info(f"Period: {from_date} to {to_date}")
    logging.info(f"Interval: {interval}")
    
    total_processed = 0
    total_saved = 0

    # Loop through symbols and fetch
    for symbol in SYMBOLS:
        token = zerodha.tokens.get(symbol)
        if not token:
            logging.warning("Skipping %s: Token not found", symbol)
            continue

        try:
            logging.info(
                "Fetching %s candles (%s) from %s to %s",
                symbol, interval, from_date, to_date
            )
            hist = zerodha.kite.historical_data(
                instrument_token=token,
                from_date=from_date,
                to_date=to_date,
                interval=interval,
                continuous=False,
            )

            saved = 0
            processed = 0
            
            for row in hist:
                processed += 1
                
                # Create MarketData object
                market_data = MarketData(
                    symbol=symbol,
                    timestamp=row["date"],
                    open=row["open"],
                    high=row["high"],
                    low=row["low"],
                    close=row["close"],
                    volume=row["volume"],
                    source="zerodha_historical",
                )
                
                # FIXED: Use unified pipeline instead of direct database access
                # This ensures historical data gets same validation and indicators as live data
                success = collector.process_and_save(market_data)
                if success:
                    saved += 1

            total_processed += processed
            total_saved += saved
            
            logging.info("%s: Processed %d candles, saved %d (%.1f%% success)", 
                        symbol, processed, saved, 
                        (saved/processed*100) if processed > 0 else 0)
            
            time.sleep(1)  # respect API rate‑limits

        except Exception as exc:
            logging.error("Error fetching %s: %s", symbol, exc)

    # Final summary
    logging.info("Historical data collection completed")
    logging.info(f"Total processed: {total_processed}")
    logging.info(f"Total saved: {total_saved}")
    logging.info(f"Overall success rate: {(total_saved/total_processed*100):.1f}%")
    
    # Generate and display collection summary
    try:
        summary = collector.generate_summary()
        logging.info("Validation statistics:")
        for key, value in summary.get('validation_stats', {}).items():
            logging.info(f"  {key}: {value}")
    except Exception as e:
        logging.warning(f"Could not generate summary: {e}")

    collector.close()


if __name__ == "__main__":
    main()
