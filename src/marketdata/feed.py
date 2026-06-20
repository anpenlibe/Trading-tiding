"""Unified market-data feed — the ingestion seam shared by backtest and live.

The decision pipeline (features → decision → risk → execution) is identical for
both run modes; only INGESTION differs. This module is that seam:

- ``MarketDataSource`` serves OHLCV bars up to a point in time (interval-aware).
  ``DatabaseSource`` reads them from the local ``price_data`` table (backtest, and
  live history). A live current-bar source wrapping ``ZerodhaAPI`` lands with the
  live runner (Phase 5) — it just implements the same interface.
- ``Feed`` wraps a source with a movable "current time" plus indicator computation,
  so both the backtest loop and the live loop consume the SAME serving logic
  instead of each reimplementing it. (The backtest *used* to reimplement it, which
  is exactly how the daily-warmup bug crept in.)
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
import sqlite3

import pandas as pd

from src.platform.types import MarketData
from src.platform.config import DB_PATH, DEFAULT_DATA_INTERVAL, DEFAULT_PERIODS, MIN_DATA_FOR_INDICATORS
from src.features.indicators import calculate_all_indicators
from src.platform.logger import setup_logger

logger = setup_logger(__name__, 'feed.log')


class MarketDataSource(ABC):
    """Serves OHLCV bars up to a point in time. Backtest vs live differ only here."""

    @abstractmethod
    def date_range(self, symbols: List[str]) -> Tuple[Optional[str], Optional[str]]:
        """(min_date, max_date) of available bars for ``symbols``, or (None, None)."""

    @abstractmethod
    def bars(self, symbol: str, periods: int = DEFAULT_PERIODS,
             end: Optional[pd.Timestamp] = None) -> pd.DataFrame:
        """Up to ``periods`` bars for ``symbol`` at/<= ``end`` (None = latest),
        oldest-first. Columns: timestamp, open, high, low, close, volume."""


class DatabaseSource(MarketDataSource):
    """Reads bars from the local ``price_data`` table for one interval.

    For a backtest it ``preload``s ``[warmup_floor, window_end]`` once (so we don't
    re-query per tick) and serves point-in-time slices from memory. The warmup
    floor is ``warmup_bars`` bars before the window start — an interval-agnostic
    bar COUNT, not a fixed "previous day" (which starved daily runs to a single bar;
    see the Phase-1 fix). Without a preload it falls back to direct point-in-time
    queries, which is how a live loop would read history from the store.
    """

    def __init__(self, db_path: str = DB_PATH, interval: str = DEFAULT_DATA_INTERVAL):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.interval = interval
        self._df: Optional[pd.DataFrame] = None
        logger.info(f"DatabaseSource initialized (interval={interval})")

    def date_range(self, symbols: List[str]) -> Tuple[Optional[str], Optional[str]]:
        placeholders = ','.join('?' for _ in symbols)
        row = self.conn.execute(
            f"SELECT MIN(DATE(timestamp)) AS s, MAX(DATE(timestamp)) AS e, COUNT(*) AS n "
            f"FROM price_data WHERE symbol IN ({placeholders}) AND interval = ?",
            symbols + [self.interval],
        ).fetchone()
        if not row or not row['s']:
            return None, None
        logger.info(f"Available data: {row['s']} to {row['e']} ({row['n']} records)")
        return row['s'], row['e']

    def preload(self, symbols: List[str], window_start: str, window_end: str,
                warmup_bars: int = DEFAULT_PERIODS) -> pd.DataFrame:
        """Load ``[warmup_floor, window_end]`` for ``symbols`` into memory."""
        placeholders = ','.join('?' for _ in symbols)
        floor_row = self.conn.execute(
            f"SELECT MIN(ts) AS f FROM (SELECT DISTINCT timestamp AS ts FROM price_data "
            f"WHERE symbol IN ({placeholders}) AND interval = ? AND timestamp < ? "
            f"ORDER BY ts DESC LIMIT ?)",
            symbols + [self.interval, window_start, warmup_bars],
        ).fetchone()
        floor = (floor_row['f'] if floor_row else None) or window_start
        logger.info(f"Indicator warmup: loading from {floor} "
                    f"(up to {warmup_bars} {self.interval} bars before window)")

        df = pd.read_sql_query(
            f"SELECT symbol, timestamp, open, high, low, close, volume, source "
            f"FROM price_data WHERE symbol IN ({placeholders}) AND interval = ? "
            f"AND timestamp >= ? AND timestamp <= ? ORDER BY timestamp ASC",
            self.conn, params=symbols + [self.interval, floor, window_end + ' 23:59:59'],
        )
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'], format='ISO8601', utc=True).dt.tz_localize(None)
        self._df = df
        logger.info(f"Loaded {len(df)} bars for {len(symbols)} symbols")
        return df

    def all_timestamps(self) -> List[pd.Timestamp]:
        """Distinct timestamps in the preloaded window (drives tick selection)."""
        return sorted(self._df['timestamp'].unique()) if self._df is not None else []

    def bars(self, symbol: str, periods: int = DEFAULT_PERIODS,
             end: Optional[pd.Timestamp] = None) -> pd.DataFrame:
        cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        if self._df is not None:
            d = self._df[self._df['symbol'] == symbol]
            if end is not None:
                d = d[d['timestamp'] <= end]
            d = d.tail(periods)
            return d[cols].copy() if not d.empty else pd.DataFrame(columns=cols)
        return self._query_bars(symbol, periods, end)

    def _query_bars(self, symbol: str, periods: int, end) -> pd.DataFrame:
        """Direct point-in-time query (used when not preloaded, e.g. live history)."""
        if end is None:
            q = ("SELECT timestamp, open, high, low, close, volume FROM price_data "
                 "WHERE symbol = ? AND interval = ? ORDER BY timestamp DESC LIMIT ?")
            params = (symbol, self.interval, periods)
        else:
            q = ("SELECT timestamp, open, high, low, close, volume FROM price_data "
                 "WHERE symbol = ? AND interval = ? AND timestamp <= ? "
                 "ORDER BY timestamp DESC LIMIT ?")
            params = (symbol, self.interval, str(end), periods)
        df = pd.read_sql_query(q, self.conn, params=params)
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'], format='mixed', errors='coerce')
            df = df.sort_values('timestamp')
        return df

    def close(self):
        if self.conn:
            self.conn.close()


class Feed:
    """Point-in-time view over a ``MarketDataSource``.

    A movable ``current_time`` plus the three reads the pipeline needs: the current
    bar, the indicator-history window, and the computed indicators. Replaces the
    backtest's ``SimulationDataCollector`` and is the read API the live loop will use.
    """

    def __init__(self, source: MarketDataSource):
        self.source = source
        self.current_time: Optional[pd.Timestamp] = None

    def set_time(self, t: pd.Timestamp):
        self.current_time = t

    def current(self, symbol: str) -> Optional[MarketData]:
        """The most recent bar at/<= current_time, as a MarketData."""
        df = self.source.bars(symbol, periods=1, end=self.current_time)
        if df.empty:
            return None
        row = df.iloc[-1]
        return MarketData(
            symbol=symbol,
            timestamp=row['timestamp'].to_pydatetime(),
            open=float(row['open']), high=float(row['high']), low=float(row['low']),
            close=float(row['close']), volume=int(row['volume']), source='feed',
        )

    def history(self, symbol: str, periods: int = DEFAULT_PERIODS) -> pd.DataFrame:
        """Up to ``periods`` bars at/<= current_time, oldest-first."""
        return self.source.bars(symbol, periods=periods, end=self.current_time)

    def indicators(self, symbol: str) -> Dict[str, float]:
        """Indicators computed over the history window (``{}`` if too few bars)."""
        df = self.history(symbol)
        if len(df) < MIN_DATA_FOR_INDICATORS:
            return {}
        return calculate_all_indicators(df)
