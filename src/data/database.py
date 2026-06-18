"""Database management for market data."""

import os
import shutil
import sqlite3
import pandas as pd
from datetime import datetime
from typing import Optional, Dict, Any

from src.interfaces import MarketData
from src.data.config import DB_PATH, BUNDLED_DB_PATH, DEFAULT_PERIODS
from src.utils.logger import setup_logger

logger = setup_logger(__name__, 'database.log')


class DatabaseManager:
    """Handle all database operations for market data."""

    def __init__(self, db_path: str = DB_PATH):
        """Initialize database connection."""
        self.db_path = db_path
        self.conn = None
        self._seed_from_bundled()
        self._init_database()

    def _seed_from_bundled(self):
        """Seed a fresh runtime DB from the committed snapshot.

        Lets the trader start with historical context while keeping all live/mock
        writes out of the version-controlled snapshot. No-op when opening the
        bundled snapshot itself or when the runtime DB already exists.
        """
        if (self.db_path != BUNDLED_DB_PATH
                and not os.path.exists(self.db_path)
                and os.path.exists(BUNDLED_DB_PATH)):
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            shutil.copy2(BUNDLED_DB_PATH, self.db_path)
            logger.info(f"Seeded runtime DB from bundled snapshot -> {self.db_path}")

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
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS price_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume INTEGER NOT NULL,
                source TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, timestamp)
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
            "CREATE INDEX IF NOT EXISTS idx_price_symbol_timestamp ON price_data(symbol, timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_indicators_symbol_timestamp ON indicators(symbol, timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_ai_decisions_symbol_time ON ai_decisions(symbol, timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_ai_decisions_signal ON ai_decisions(signal)",
            "CREATE INDEX IF NOT EXISTS idx_ai_decisions_outcome ON ai_decisions(outcome)",
            "CREATE INDEX IF NOT EXISTS idx_api_costs_timestamp ON api_costs(timestamp DESC)",
        ):
            self.conn.execute(stmt)

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

    def save_market_data(self, data: MarketData) -> bool:
        """Insert or replace one OHLCV bar."""
        try:
            self.conn.execute('''
                INSERT OR REPLACE INTO price_data
                (symbol, timestamp, open, high, low, close, volume, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data.symbol, self._to_timestamp_str(data.timestamp),
                data.open, data.high, data.low, data.close, data.volume,
                getattr(data, 'source', 'unknown'),
            ))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save market data for {data.symbol}: {e}")
            return False

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

    def get_recent_data(self, symbol: str, periods: int = DEFAULT_PERIODS) -> pd.DataFrame:
        """Get the most recent `periods` bars for a symbol, oldest-first."""
        query = '''
            SELECT timestamp, open, high, low, close, volume
            FROM price_data
            WHERE symbol = ?
            ORDER BY timestamp DESC
            LIMIT ?
        '''
        df = pd.read_sql_query(query, self.conn, params=(symbol, periods))
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'], format='mixed', errors='coerce')
            df = df.sort_values('timestamp')
        return df

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
