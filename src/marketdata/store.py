"""Database management for market data."""

import os
import sqlite3
import pandas as pd
from datetime import datetime
from typing import Optional, Dict, Any

from src.platform.types import MarketData
from src.platform.config import DB_PATH, DEFAULT_PERIODS, DEFAULT_DATA_INTERVAL
from src.platform.logger import setup_logger

logger = setup_logger(__name__, 'database.log')


class DatabaseManager:
    """Handle all database operations for market data."""

    def __init__(self, db_path: str = DB_PATH):
        """Initialize database connection."""
        self.db_path = db_path
        self.conn = None
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_database()

    def _init_database(self):
        """Open the connection, set pragmas, and create tables."""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA synchronous=NORMAL")
            self._create_tables()
            logger.info(f"Database initialized: {self.db_path}")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise

    def _create_tables(self):
        """Create required database tables and indexes."""
        # Migrate any pre-interval price_data before (re)creating the table.
        self._migrate_price_data_schema()

        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS price_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                interval TEXT NOT NULL DEFAULT '1d',
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume INTEGER NOT NULL,
                source TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, timestamp, interval)
            )
        ''')

        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS indicators (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                sma_20 REAL,
                sma_50 REAL,
                sma_200 REAL,
                rsi_14 REAL,
                macd REAL,
                macd_signal REAL,
                macd_histogram REAL,
                volume_avg_20 REAL,
                price_change_pct REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, timestamp)
            )
        ''')

        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS data_quality_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                symbol TEXT,
                issue_type TEXT,
                description TEXT,
                severity TEXT
            )
        ''')

        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS ai_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                symbol TEXT NOT NULL,
                signal TEXT NOT NULL,
                confidence REAL NOT NULL,
                reasoning TEXT,
                price REAL,
                rsi REAL,
                macd REAL,
                volume REAL,
                outcome TEXT,
                profit_loss REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS api_costs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                context TEXT,
                prompt_tokens INTEGER NOT NULL,
                response_tokens INTEGER NOT NULL,
                cost REAL NOT NULL,
                response_time REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        for stmt in (
            "CREATE INDEX IF NOT EXISTS idx_price_symbol_interval_ts ON price_data(symbol, interval, timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_indicators_symbol_timestamp ON indicators(symbol, timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_ai_decisions_symbol_time ON ai_decisions(symbol, timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_ai_decisions_signal ON ai_decisions(signal)",
            "CREATE INDEX IF NOT EXISTS idx_ai_decisions_outcome ON ai_decisions(outcome)",
            "CREATE INDEX IF NOT EXISTS idx_api_costs_timestamp ON api_costs(timestamp DESC)",
        ):
            self.conn.execute(stmt)

        self.conn.commit()

    def _migrate_price_data_schema(self):
        """Drop a pre-interval price_data table so it can be recreated with the
        interval column + UNIQUE(symbol, timestamp, interval).

        The old schema keyed UNIQUE(symbol, timestamp) and held a single interval
        (5m), which collides once multiple intervals share the table. The legacy
        rows are disposable (re-downloaded), so we drop rather than backfill.
        """
        exists = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='price_data'"
        ).fetchone()
        if not exists:
            return
        cols = [r['name'] for r in self.conn.execute("PRAGMA table_info(price_data)")]
        if 'interval' not in cols:
            n = self.conn.execute("SELECT COUNT(*) FROM price_data").fetchone()[0]
            logger.warning(
                "Migrating price_data to interval-aware schema: dropping %d legacy "
                "single-interval rows (re-download via runners/download.py)", n,
            )
            self.conn.execute("DROP TABLE price_data")
            self.conn.commit()

    @staticmethod
    def _to_timestamp_str(timestamp) -> str:
        """Normalize a datetime or string to the on-disk 'YYYY-MM-DD HH:MM:SS'
        format (naive, second precision) used by every table.

        This is why db_optimizer.cleanup_old_data can compare timestamps as plain
        strings — all writes funnel through here.
        """
        if hasattr(timestamp, 'isoformat'):  # datetime
            if getattr(timestamp, 'tzinfo', None) is not None:
                timestamp = timestamp.replace(tzinfo=None)
            return timestamp.strftime('%Y-%m-%d %H:%M:%S')
        if isinstance(timestamp, str):
            if 'T' in timestamp or '+' in timestamp:  # ISO / tz-aware string
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00')).replace(tzinfo=None)
                    return dt.strftime('%Y-%m-%d %H:%M:%S')
                except ValueError:
                    return str(timestamp)[:19]  # best-effort YYYY-MM-DD HH:MM:SS
            return timestamp
        return str(timestamp)

    @staticmethod
    def _bucket_timestamp(timestamp, interval: str):
        """Snap a live bar's timestamp to its interval bucket.

        A live quote is stamped with wall-clock 'now', but it represents the bar
        currently FORMING for its interval: a '1d' quote is today's daily candle
        (open fixed, high/low/close/volume still evolving until the close), a '5m'
        quote is the current 5-minute candle. Because the UNIQUE key includes the
        timestamp, keying every tick at HH:MM:SS made INSERT-OR-REPLACE APPEND a
        fresh row each cycle — so the '1d' series filled with intraday snapshots
        and indicators read a mix of daily closes and same-day ticks. Snapping to
        the bucket makes successive ticks OVERWRITE the period's single row in
        place (one bar per period), which is how a candle actually forms.

        Returns a naive ``pd.Timestamp``; ``_to_timestamp_str`` formats it.
        """
        ts = pd.Timestamp(timestamp)
        if ts.tzinfo is not None:
            ts = ts.tz_localize(None)
        if interval == "1d":
            return ts.normalize()  # 00:00:00 of the trading date
        minutes = {"1m": 1, "5m": 5, "15m": 15, "30m": 30}.get(interval)
        return ts.floor(f"{minutes}min") if minutes else ts

    def save_market_data(self, data: MarketData, interval: str = DEFAULT_DATA_INTERVAL) -> bool:
        """Insert or replace one OHLCV bar for the given interval.

        The timestamp is bucketed to the interval (see ``_bucket_timestamp``) so a
        live bar updated each tick overwrites the period's single row rather than
        appending — keeping e.g. the daily series one-row-per-day.
        """
        try:
            bucketed = self._bucket_timestamp(data.timestamp, interval)
            self.conn.execute('''
                INSERT OR REPLACE INTO price_data
                (symbol, timestamp, interval, open, high, low, close, volume, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data.symbol, self._to_timestamp_str(bucketed), interval,
                data.open, data.high, data.low, data.close, data.volume,
                getattr(data, 'source', 'unknown'),
            ))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save market data for {data.symbol}: {e}")
            return False

    def save_bars_bulk(self, bars, interval: str, source: str = 'zerodha_historical') -> int:
        """Bulk insert-or-replace OHLCV bars for one interval in a single commit.

        ``bars`` is an iterable of dicts/rows with keys
        ``symbol, date|timestamp, open, high, low, close, volume``. Used by the
        historical collector: one executemany per chunk instead of a per-bar
        SELECT + indicator recompute (orders of magnitude faster for ~1M rows).
        """
        rows = [
            (
                b['symbol'], self._to_timestamp_str(b.get('timestamp', b.get('date'))), interval,
                b['open'], b['high'], b['low'], b['close'], int(b['volume']), source,
            )
            for b in bars
        ]
        if not rows:
            return 0
        self.conn.executemany('''
            INSERT OR REPLACE INTO price_data
            (symbol, timestamp, interval, open, high, low, close, volume, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', rows)
        self.conn.commit()
        return len(rows)

    def save_indicators(self, symbol: str, timestamp: datetime, indicators: Dict[str, float]) -> bool:
        """Insert or replace the indicator row for a symbol at a timestamp."""
        try:
            self.conn.execute('''
                INSERT OR REPLACE INTO indicators
                (symbol, timestamp, sma_20, sma_50, sma_200, rsi_14,
                 macd, macd_signal, macd_histogram, volume_avg_20, price_change_pct)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                symbol, self._to_timestamp_str(timestamp),
                indicators.get('sma_20'), indicators.get('sma_50'), indicators.get('sma_200'),
                indicators.get('rsi_14'), indicators.get('macd'), indicators.get('macd_signal'),
                indicators.get('macd_histogram'), indicators.get('volume_avg_20'),
                indicators.get('price_change_pct'),
            ))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save indicators for {symbol}: {e}")
            return False

    def get_recent_data(self, symbol: str, periods: int = DEFAULT_PERIODS,
                        interval: str = DEFAULT_DATA_INTERVAL) -> pd.DataFrame:
        """Get the most recent `periods` bars for a symbol/interval, oldest-first."""
        query = '''
            SELECT timestamp, open, high, low, close, volume
            FROM price_data
            WHERE symbol = ? AND interval = ?
            ORDER BY timestamp DESC
            LIMIT ?
        '''
        df = pd.read_sql_query(query, self.conn, params=(symbol, interval, periods))
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'], format='mixed', errors='coerce')
            df = df.sort_values('timestamp')
        return df

    def get_previous_close(self, symbol: str, interval: str = DEFAULT_DATA_INTERVAL) -> Optional[float]:
        """Most recent stored close for `symbol`/interval, or None if none yet.

        Feeds the validator's price-jump circuit breaker: when a new bar arrives,
        comparing it to this previous close catches discontinuities (e.g. a stale
        or bad bar that teleports price) before they pollute the indicator window.
        """
        row = self.conn.execute(
            "SELECT close FROM price_data WHERE symbol = ? AND interval = ? "
            "ORDER BY timestamp DESC LIMIT 1",
            (symbol, interval),
        ).fetchone()
        return row['close'] if row else None

    def get_stats(self) -> Dict[str, int]:
        """Get database statistics (record + symbol counts)."""
        stats = {}
        try:
            stats['total_price_records'] = self.conn.execute(
                "SELECT COUNT(*) FROM price_data").fetchone()[0]
            stats['total_indicator_records'] = self.conn.execute(
                "SELECT COUNT(*) FROM indicators").fetchone()[0]
            stats['unique_symbols'] = self.conn.execute(
                "SELECT COUNT(DISTINCT symbol) FROM price_data").fetchone()[0]
        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
        return stats

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")
