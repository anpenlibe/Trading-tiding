"""Database optimization utilities."""

import sqlite3
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List
from src.config import DB_PATH
from src.utils.logger import setup_logger

logger = setup_logger(__name__, 'db_optimizer.log')


class DatabaseOptimizer:
    """Database optimization and maintenance."""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        
    def analyze_performance(self) -> Dict[str, Any]:
        """Analyze database performance metrics."""
        metrics = {}
        
        # Database size
        cur = self.conn.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
        metrics['size_bytes'] = cur.fetchone()['size']
        metrics['size_mb'] = metrics['size_bytes'] / (1024 * 1024)
        
        # Table statistics
        tables = ['price_data', 'indicators', 'data_quality_log']
        metrics['tables'] = {}
        
        for table in tables:
            try:
                count = self.conn.execute(f"SELECT COUNT(*) as cnt FROM {table}").fetchone()['cnt']
                metrics['tables'][table] = count
            except:
                metrics['tables'][table] = 0
        
        # Index usage
        metrics['indexes'] = []
        cur = self.conn.execute("SELECT name, tbl_name FROM sqlite_master WHERE type='index'")
        for row in cur:
            metrics['indexes'].append({'name': row['name'], 'table': row['tbl_name']})
        
        return metrics
    
    def optimize_indexes(self) -> List[str]:
        """Create optimal indexes for common queries."""
        optimizations = []
        
        # Critical indexes for performance
        indexes = [
            # Price data indexes
            ("idx_price_symbol_timestamp", "price_data", "(symbol, timestamp DESC)"),
            ("idx_price_timestamp", "price_data", "(timestamp DESC)"),
            ("idx_price_symbol", "price_data", "(symbol)"),
            
            # Indicator indexes
            ("idx_indicators_symbol_timestamp", "indicators", "(symbol, timestamp DESC)"),
            ("idx_indicators_name", "indicators", "(indicator_name)"),
            
            # Data quality indexes
            ("idx_quality_timestamp", "data_quality_log", "(timestamp DESC)"),
            ("idx_quality_symbol", "data_quality_log", "(symbol)")
        ]
        
        for index_name, table, columns in indexes:
            try:
                # Check if index exists
                cur = self.conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                    (index_name,)
                )
                
                if not cur.fetchone():
                    # Create index
                    self.conn.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} {columns}")
                    optimizations.append(f"Created index: {index_name}")
                    logger.info(f"Created index: {index_name}")
            except Exception as e:
                logger.error(f"Failed to create index {index_name}: {e}")
        
        self.conn.commit()
        return optimizations
    
    def vacuum_database(self) -> Dict[str, Any]:
        """Vacuum database to reclaim space and optimize."""
        metrics_before = self.analyze_performance()
        
        logger.info("Starting database vacuum...")
        self.conn.execute("VACUUM")
        self.conn.execute("ANALYZE")  # Update statistics
        
        metrics_after = self.analyze_performance()
        
        result = {
            'size_before_mb': metrics_before['size_mb'],
            'size_after_mb': metrics_after['size_mb'],
            'space_saved_mb': metrics_before['size_mb'] - metrics_after['size_mb']
        }
        
        logger.info(f"Vacuum complete. Saved {result['space_saved_mb']:.2f} MB")
        return result
    
    def cleanup_old_data(self, days_to_keep: int = 90) -> int:
        """Remove old data beyond retention period."""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        # Count records to delete
        cur = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM price_data WHERE timestamp < ?",
            (cutoff_date,)
        )
        records_to_delete = cur.fetchone()['cnt']
        
        if records_to_delete > 0:
            # Delete old price data
            self.conn.execute("DELETE FROM price_data WHERE timestamp < ?", (cutoff_date,))
            
            # Delete old indicators
            self.conn.execute("DELETE FROM indicators WHERE timestamp < ?", (cutoff_date,))
            
            # Delete old quality logs
            self.conn.execute("DELETE FROM data_quality_log WHERE timestamp < ?", (cutoff_date,))
            
            self.conn.commit()
            logger.info(f"Cleaned up {records_to_delete} old records")
        
        return records_to_delete
    
    def optimize_settings(self):
        """Apply optimal SQLite settings."""
        optimizations = [
            "PRAGMA journal_mode = WAL",  # Write-Ahead Logging
            "PRAGMA synchronous = NORMAL",  # Balance safety/speed
            "PRAGMA cache_size = -64000",  # 64MB cache
            "PRAGMA temp_store = MEMORY",  # Use memory for temp tables
            "PRAGMA mmap_size = 268435456",  # 256MB memory-mapped I/O
            "PRAGMA optimize"  # Run optimization
        ]
        
        for pragma in optimizations:
            self.conn.execute(pragma)
            logger.info(f"Applied: {pragma}")
    
    def close(self):
        """Close connection."""
        self.conn.close()


def run_optimization():
    """Run complete database optimization."""
    print("=" * 60)
    print("DATABASE OPTIMIZATION")
    print("=" * 60)
    
    optimizer = DatabaseOptimizer()
    
    # Analyze current state
    print("\n📊 Current Database Metrics:")
    metrics = optimizer.analyze_performance()
    print(f"  Size: {metrics['size_mb']:.2f} MB")
    for table, count in metrics['tables'].items():
        print(f"  {table}: {count:,} records")
    
    # Optimize indexes
    print("\n🔧 Optimizing Indexes...")
    optimizations = optimizer.optimize_indexes()
    for opt in optimizations:
        print(f"  ✅ {opt}")
    
    # Apply settings
    print("\n⚙️ Applying Optimal Settings...")
    optimizer.optimize_settings()
    print("  ✅ Settings optimized")
    
    # Cleanup old data
    print("\n🧹 Cleaning Old Data...")
    deleted = optimizer.cleanup_old_data(days_to_keep=90)
    print(f"  ✅ Removed {deleted:,} old records")
    
    # Vacuum
    print("\n🗜️ Vacuuming Database...")
    vacuum_result = optimizer.vacuum_database()
    print(f"  ✅ Saved {vacuum_result['space_saved_mb']:.2f} MB")
    
    # Final metrics
    print("\n📊 Final Database Metrics:")
    metrics = optimizer.analyze_performance()
    print(f"  Size: {metrics['size_mb']:.2f} MB")
    print(f"  Indexes: {len(metrics['indexes'])}")
    
    optimizer.close()
    print("\n✅ Optimization Complete!")

if __name__ == "__main__":
    run_optimization()