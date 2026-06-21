"""Historical backfill — shared by the download runner and the live runner.

Pulls missing OHLCV candles from Zerodha into the interval-aware ``price_data``
table so the feature layer can warm up its indicators. Two entry points over the
same chunked fetch:

- ``download_range`` — fetch one symbol over an explicit [from, to] window. Used
  by ``runners/download.py`` for bulk backfills.
- ``ensure_recent_history`` — gap-aware startup fill: for each symbol, download
  from just after its latest stored bar (or the lookback floor) up to now. The
  live runner calls this before its loop so a cold/stale DB still yields
  correctly-warmed indicators on the first tick.

Zerodha caps the historical range per request by interval, so windows are split
into chunks. ``save_bars_bulk`` is INSERT-OR-REPLACE on UNIQUE(symbol, timestamp,
interval), so any overlap from a generous floor is idempotent — we never need
exact per-bar bookkeeping.
"""

import time
from datetime import datetime, timedelta
from typing import List, Optional

import pandas as pd

from src.marketdata.sources import ZerodhaAPI
from src.marketdata.store import DatabaseManager
from src.platform.config import DB_PATH, DEFAULT_DATA_INTERVAL
from src.platform.logger import setup_logger

logger = setup_logger(__name__, 'backfill.log')

# Our interval labels → Zerodha interval names and per-request day caps.
# Zerodha limits: minute=60d, 3–30min=100d, day=2000d. We stay just under.
ZERODHA_INTERVAL = {"1m": "minute", "5m": "5minute", "15m": "15minute",
                    "30m": "30minute", "1d": "day"}
MAX_CHUNK_DAYS = {"1m": 58, "5m": 95, "15m": 95, "30m": 95, "1d": 1900}


def date_chunks(from_date: datetime, to_date: datetime, max_days: int):
    """Yield (chunk_from, chunk_to) windows no longer than ``max_days``."""
    cur = from_date
    while cur < to_date:
        nxt = min(cur + timedelta(days=max_days), to_date)
        yield cur, nxt
        cur = nxt


def download_range(zerodha: ZerodhaAPI, db: DatabaseManager, symbol: str,
                   from_date: datetime, to_date: datetime,
                   interval: str = DEFAULT_DATA_INTERVAL) -> int:
    """Fetch [from_date, to_date] candles for one ``symbol`` and bulk-save.

    Returns the number of rows written. Splits the window into Zerodha-legal
    chunks and sleeps between calls to respect the ~3 req/s historical limit.
    """
    token = zerodha.tokens.get(symbol)
    if not token:
        logger.warning("Skipping %s: no instrument token", symbol)
        return 0

    zint = ZERODHA_INTERVAL[interval]
    max_days = MAX_CHUNK_DAYS[interval]
    saved = 0
    for cfrom, cto in date_chunks(from_date, to_date, max_days):
        try:
            hist = zerodha.kite.historical_data(token, cfrom, cto, zint, continuous=False)
        except Exception as exc:
            logger.error("  %s %s→%s: %s", symbol, cfrom.date(), cto.date(), exc)
            continue
        for row in hist:
            row["symbol"] = symbol
        saved += db.save_bars_bulk(hist, interval=interval)
        time.sleep(0.4)  # respect Zerodha historical rate limit (~3 req/s)
    return saved


def _latest_bar(db: DatabaseManager, symbol: str, interval: str) -> Optional[datetime]:
    """Most recent stored bar timestamp for symbol/interval, or None if none yet."""
    row = db.conn.execute(
        "SELECT MAX(timestamp) AS t FROM price_data WHERE symbol = ? AND interval = ?",
        (symbol, interval),
    ).fetchone()
    if not row or not row["t"]:
        return None
    ts = pd.to_datetime(str(row["t"]), errors="coerce")
    return None if pd.isna(ts) else ts.to_pydatetime()


def ensure_recent_history(symbols: List[str], lookback_days: int = 60,
                          interval: str = DEFAULT_DATA_INTERVAL,
                          zerodha: Optional[ZerodhaAPI] = None,
                          db: Optional[DatabaseManager] = None) -> int:
    """Ensure each symbol has bars covering roughly the last ``lookback_days``.

    For each symbol we download from just after its latest stored bar (or from the
    lookback floor if it has none/older data) up to now. Symbols already current
    are skipped. Requires an authenticated Zerodha session; logs and returns 0 if
    unavailable rather than raising — a backfill miss shouldn't abort startup.

    ``zerodha`` / ``db`` may be passed in to reuse an existing session/connection
    (the live runner does this to avoid a second auth probe). Any connection this
    function opens itself is closed before returning.
    """
    own_db = db is None
    zerodha = zerodha or ZerodhaAPI()
    if not zerodha.is_authenticated:
        logger.warning("Backfill skipped: Zerodha not authenticated "
                       "(refresh via scripts/generate_zerodha_token.py)")
        return 0

    db = db or DatabaseManager(DB_PATH)
    now = datetime.now()
    floor = now - timedelta(days=lookback_days)
    logger.info("Ensuring ~%dd of %s history for %d symbols (floor %s)",
                lookback_days, interval, len(symbols), floor.date())

    total = 0
    try:
        for symbol in symbols:
            latest = _latest_bar(db, symbol, interval)
            if latest is not None and latest.date() >= now.date():
                logger.info("  %-12s up to date (latest %s)", symbol, latest.date())
                continue
            start = floor if latest is None else max(floor, latest + timedelta(days=1))
            n = download_range(zerodha, db, symbol, start, now, interval)
            total += n
            logger.info("  %-12s backfilled %d %s bars from %s",
                        symbol, n, interval, start.date())
    finally:
        if own_db:
            db.close()

    logger.info("Backfill complete: %d %s bars across %d symbols",
                total, interval, len(symbols))
    return total
