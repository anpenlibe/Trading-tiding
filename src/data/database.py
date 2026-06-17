"""Database management for market data."""

import os
import shutil
import sqlite3
import pandas as pd
import time
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
        """Initialize database with required tables."""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            
            # Enable WAL mode for better performance
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA synchronous=NORMAL")
            
            # Create tables
            self._create_tables()
            
            logger.info(f"Database initialized: {self.db_path}")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise
    
    def _create_tables(self):
        """Create required database tables."""
        # Price data table
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
        
        # Indicators table
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
        
        # Data quality log
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
        
        # AI Decisions table for persistent memory
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
        
        # API Cost tracking table for robust persistence
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
        
        # Create indexes
        self.conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_price_symbol_timestamp 
            ON price_data(symbol, timestamp DESC)
        ''')
        self.conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_indicators_symbol_timestamp 
            ON indicators(symbol, timestamp DESC)
        ''')
        self.conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_ai_decisions_symbol_time 
            ON ai_decisions(symbol, timestamp)
        ''')
        self.conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_ai_decisions_signal 
            ON ai_decisions(signal)
        ''')
        self.conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_ai_decisions_outcome 
            ON ai_decisions(outcome)
        ''')
        self.conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_api_costs_timestamp 
            ON api_costs(timestamp DESC)
        ''')
        
        self.conn.commit()
    
    def insert_price_data(self, symbol: str, data: Dict[str, Any]) -> bool:
        """Insert or update price data with flexible timestamp handling."""
        try:
            # Handle various timestamp formats
            timestamp = data['timestamp']
            
            # Convert to string format for database
            if hasattr(timestamp, 'isoformat'):
                # It's a datetime object
                if hasattr(timestamp, 'tzinfo') and timestamp.tzinfo is not None:
                    # Remove timezone info for SQLite
                    timestamp = timestamp.replace(tzinfo=None)
                timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
            elif isinstance(timestamp, str):
                # It's already a string - parse and reformat if needed
                if '+' in timestamp or 'T' in timestamp:
                    # ISO format with timezone - parse and convert
                    from datetime import datetime
                    try:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        dt = dt.replace(tzinfo=None)  # Remove timezone
                        timestamp_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        # Fallback for non-standard ISO formats
                        timestamp_str = str(timestamp)[:19]  # Keep only YYYY-MM-DD HH:MM:SS
                else:
                    timestamp_str = timestamp
            else:
                timestamp_str = str(timestamp)
            
            self.conn.execute('''
                INSERT OR REPLACE INTO price_data 
                (symbol, timestamp, open, high, low, close, volume, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                symbol, timestamp_str, data['open'], data['high'],
                data['low'], data['close'], data['volume'], 
                data.get('source', 'unknown')
            ))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to insert price data for {symbol}: {e}")
            return False
    
    def save_market_data(self, data: MarketData) -> bool:
        """Save market data to database."""
        try:
            # Use the same timestamp handling as insert_price_data
            timestamp = data.timestamp
            
            # Convert to string format for database
            if hasattr(timestamp, 'isoformat'):
                # It's a datetime object
                if hasattr(timestamp, 'tzinfo') and timestamp.tzinfo is not None:
                    # Remove timezone info for SQLite
                    timestamp = timestamp.replace(tzinfo=None)
                timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
            elif isinstance(timestamp, str):
                # It's already a string - parse and reformat if needed
                if '+' in timestamp or 'T' in timestamp:
                    # ISO format with timezone - parse and convert
                    try:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        dt = dt.replace(tzinfo=None)  # Remove timezone
                        timestamp_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        # Fallback for non-standard ISO formats
                        timestamp_str = str(timestamp)[:19]  # Keep only YYYY-MM-DD HH:MM:SS
                else:
                    timestamp_str = timestamp
            else:
                timestamp_str = str(timestamp)
            
            self.conn.execute('''
                INSERT OR REPLACE INTO price_data 
                (symbol, timestamp, open, high, low, close, volume, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data.symbol, timestamp_str, data.open, data.high,
                data.low, data.close, data.volume, 
                getattr(data, 'source', 'unknown')
            ))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save market data for {data.symbol}: {e}")
            return False
    
    def save_indicators(self, symbol: str, timestamp: datetime, indicators: Dict[str, float]) -> bool:
        """Save calculated indicators to database."""
        try:
            # Use the same timestamp handling as save_market_data
            if hasattr(timestamp, 'isoformat'):
                # It's a datetime object
                if hasattr(timestamp, 'tzinfo') and timestamp.tzinfo is not None:
                    # Remove timezone info for SQLite
                    timestamp = timestamp.replace(tzinfo=None)
                timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
            elif isinstance(timestamp, str):
                # It's already a string - parse and reformat if needed
                if '+' in timestamp or 'T' in timestamp:
                    # ISO format with timezone - parse and convert
                    try:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        dt = dt.replace(tzinfo=None)  # Remove timezone
                        timestamp_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        # Fallback for non-standard ISO formats
                        timestamp_str = str(timestamp)[:19]  # Keep only YYYY-MM-DD HH:MM:SS
                else:
                    timestamp_str = timestamp
            else:
                timestamp_str = str(timestamp)
            
            self.conn.execute('''
                INSERT OR REPLACE INTO indicators 
                (symbol, timestamp, sma_20, sma_50, sma_200, rsi_14, 
                 macd, macd_signal, macd_histogram, volume_avg_20, price_change_pct)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                symbol, timestamp_str,
                indicators.get('sma_20'), indicators.get('sma_50'), indicators.get('sma_200'),
                indicators.get('rsi_14'), indicators.get('macd'), indicators.get('macd_signal'),
                indicators.get('macd_histogram'), indicators.get('volume_avg_20'),
                indicators.get('price_change_pct')
            ))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save indicators for {symbol}: {e}")
            return False
    
    def get_recent_data(self, symbol: str, periods: int = DEFAULT_PERIODS) -> pd.DataFrame:
        """Get recent price data for a symbol."""
        query = '''
            SELECT timestamp, open, high, low, close, volume
            FROM price_data
            WHERE symbol = ?
            ORDER BY timestamp DESC
            LIMIT ?
        '''
        
        df = pd.read_sql_query(query, self.conn, params=(symbol, periods))
        if not df.empty:
            # Handle timestamp parsing with flexible format
            df['timestamp'] = pd.to_datetime(df['timestamp'], format='mixed', errors='coerce')
            df = df.sort_values('timestamp')
        return df
    
    def get_previous_close(self, symbol: str) -> Optional[float]:
        """Get previous closing price for validation."""
        query = '''
            SELECT close 
            FROM price_data 
            WHERE symbol = ? 
            ORDER BY timestamp DESC 
            LIMIT 1
        '''
        
        result = self.conn.execute(query, (symbol,)).fetchone()
        return result['close'] if result else None
    
    def log_data_quality_issue(self, symbol: str, issue_type: str, 
                               description: str, severity: str = "WARNING"):
        """Log data quality issues."""
        try:
            self.conn.execute('''
                INSERT INTO data_quality_log (symbol, issue_type, description, severity)
                VALUES (?, ?, ?, ?)
            ''', (symbol, issue_type, description, severity))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Failed to log data quality issue: {e}")
    
    def get_stats(self) -> Dict[str, int]:
        """Get database statistics."""
        stats = {}
        try:
            # Count total records
            result = self.conn.execute("SELECT COUNT(*) FROM price_data").fetchone()
            stats['total_price_records'] = result[0]
            
            result = self.conn.execute("SELECT COUNT(*) FROM indicators").fetchone()
            stats['total_indicator_records'] = result[0]
            
            # Count symbols
            result = self.conn.execute("SELECT COUNT(DISTINCT symbol) FROM price_data").fetchone()
            stats['unique_symbols'] = result[0]
            
        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
        
        return stats
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")