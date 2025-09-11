#!/usr/bin/env python3
"""
Module: monitor.py
Purpose: Monitor data collection status and quality
Author: Trading Bot Developer
Created: 2025-06-12
Modified: 2025-06-12
"""

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from tabulate import tabulate
import sys
import os
import argparse

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.config import DB_PATH, SYMBOLS


class DataMonitor:
    """Monitor data collection status and quality"""
    
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.row_factory = sqlite3.Row
    
    def get_collection_status(self):
        """Get current collection status for all symbols"""
        query = '''
            SELECT 
                symbol,
                COUNT(*) as total_records,
                MIN(timestamp) as first_record,
                MAX(timestamp) as last_record,
                ROUND(AVG(close), 2) as avg_price,
                MAX(volume) as max_volume
            FROM price_data
            WHERE timestamp >= datetime('now', '-7 days')
            GROUP BY symbol
            ORDER BY symbol
        '''
        
        df = pd.read_sql_query(query, self.conn)
        return df
    
    def get_data_quality_stats(self):
        """Get data quality statistics"""
        query = '''
            SELECT 
                COUNT(DISTINCT symbol) as symbols_tracked,
                COUNT(*) as total_issues,
                COUNT(CASE WHEN severity = 'ERROR' THEN 1 END) as errors,
                COUNT(CASE WHEN severity = 'WARNING' THEN 1 END) as warnings
            FROM data_quality_log
            WHERE timestamp >= datetime('now', '-1 day')
        '''
        
        return self.conn.execute(query).fetchone()
    
    def get_missing_data(self):
        """Check for missing data in last 24 hours"""
        # Expected records per symbol (assuming 5-min intervals during 6.25 hour market)
        expected_per_day = 75  # 6.25 hours * 12 intervals per hour
        
        query = '''
            SELECT 
                symbol,
                COUNT(*) as actual_records,
                ? - COUNT(*) as missing_records
            FROM price_data
            WHERE DATE(timestamp) = DATE('now')
            GROUP BY symbol
            HAVING actual_records < ?
        '''
        
        df = pd.read_sql_query(query, self.conn, params=(expected_per_day, expected_per_day))
        return df
    
    def get_latest_prices(self):
        """Get latest prices for all symbols"""
        query = '''
            WITH latest_data AS (
                SELECT 
                    symbol,
                    close,
                    timestamp,
                    ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY timestamp DESC) as rn
                FROM price_data
            )
            SELECT 
                symbol,
                close as last_price,
                timestamp as last_update,
                ROUND((strftime('%s', 'now') - strftime('%s', timestamp)) / 60.0, 1) as minutes_ago
            FROM latest_data
            WHERE rn = 1
            ORDER BY symbol
        '''
        
        df = pd.read_sql_query(query, self.conn)
        return df
    
    def get_indicator_status(self):
        """Check indicator calculation status"""
        query = '''
            SELECT 
                symbol,
                COUNT(*) as total_indicators,
                COUNT(sma_20) as sma_20_count,
                COUNT(rsi_14) as rsi_14_count,
                COUNT(macd) as macd_count,
                MAX(timestamp) as last_calculated
            FROM indicators
            WHERE timestamp >= datetime('now', '-1 day')
            GROUP BY symbol
            ORDER BY symbol
        '''
        
        df = pd.read_sql_query(query, self.conn)
        return df
    
    def display_dashboard(self):
        """Display monitoring dashboard"""
        print("\n" + "="*80)
        print("TRADING BOT DATA MONITORING DASHBOARD")
        print("="*80)
        print(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Collection Status
        print("\n📊 COLLECTION STATUS (Last 7 Days)")
        print("-"*80)
        status_df = self.get_collection_status()
        if not status_df.empty:
            print(tabulate(status_df, headers='keys', tablefmt='grid', showindex=False))
        else:
            print("No data collected yet")
        
        # Latest Prices
        print("\n💰 LATEST PRICES")
        print("-"*80)
        prices_df = self.get_latest_prices()
        if not prices_df.empty:
            # Add status indicator
            prices_df['status'] = prices_df['minutes_ago'].apply(
                lambda x: '🟢' if x < 10 else ('🟡' if x < 60 else '🔴')
            )
            print(tabulate(prices_df, headers='keys', tablefmt='grid', showindex=False))
        else:
            print("No price data available")
        
        # Data Quality
        print("\n✅ DATA QUALITY (Last 24 Hours)")
        print("-"*80)
        quality = self.get_data_quality_stats()
        if quality:
            print(f"Symbols Tracked: {quality['symbols_tracked']}")
            print(f"Total Issues: {quality['total_issues']}")
            print(f"  - Errors: {quality['errors']}")
            print(f"  - Warnings: {quality['warnings']}")
        
        # Missing Data
        print("\n⚠️  MISSING DATA (Today)")
        print("-"*80)
        missing_df = self.get_missing_data()
        if not missing_df.empty:
            print(tabulate(missing_df, headers='keys', tablefmt='grid', showindex=False))
        else:
            print("No missing data detected")
        
        # Indicator Status
        print("\n📈 INDICATOR CALCULATION STATUS (Last 24 Hours)")
        print("-"*80)
        indicator_df = self.get_indicator_status()
        if not indicator_df.empty:
            print(tabulate(indicator_df, headers='keys', tablefmt='grid', showindex=False))
        else:
            print("No indicators calculated yet")
        
        print("\n" + "="*80)
    
    def check_alerts(self):
        """Check for conditions that need attention"""
        alerts = []
        
        # Check for stale data (no updates in last hour during market hours)
        query = '''
            SELECT symbol, MAX(timestamp) as last_update
            FROM price_data
            GROUP BY symbol
            HAVING datetime(last_update) < datetime('now', '-1 hour')
        '''
        
        stale_symbols = self.conn.execute(query).fetchall()
        if stale_symbols:
            alerts.append(f"⚠️  STALE DATA: {', '.join([s['symbol'] for s in stale_symbols])}")
        
        # Check for symbols with no data today
        query = '''
            SELECT symbol 
            FROM (SELECT DISTINCT ? as symbol) 
            WHERE symbol NOT IN (
                SELECT DISTINCT symbol 
                FROM price_data 
                WHERE DATE(timestamp) = DATE('now')
            )
        '''
        
        for symbol in SYMBOLS:
            no_data = self.conn.execute(query, (symbol,)).fetchone()
            if no_data:
                alerts.append(f"❌ NO DATA TODAY: {symbol}")
        
        # Check for high error rate
        quality = self.get_data_quality_stats()
        if quality and quality['errors'] > 10:
            alerts.append(f"🚨 HIGH ERROR RATE: {quality['errors']} errors in last 24h")
        
        if alerts:
            print("\n🚨 ALERTS")
            print("-"*80)
            for alert in alerts:
                print(alert)
        else:
            print("\n✅ All systems operational")
    
    def export_daily_report(self, filepath: str = None):
        """Export daily report to CSV"""
        if not filepath:
            filepath = f"data/reports/daily_report_{datetime.now().strftime('%Y%m%d')}.csv"
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # Get all today's data
        query = '''
            SELECT * FROM price_data
            WHERE DATE(timestamp) = DATE('now')
            ORDER BY symbol, timestamp
        '''
        
        df = pd.read_sql_query(query, self.conn)
        df.to_csv(filepath, index=False)
        
        print(f"\n📄 Daily report exported to: {filepath}")
        print(f"   Records: {len(df)}")
        print(f"   Symbols: {df['symbol'].nunique()}")
    
    def close(self):
        """Close database connection"""
        self.conn.close()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Trading system data monitoring dashboard')
    parser.add_argument('--auto', action='store_true', help='Run in automated mode without prompts')
    parser.add_argument('--export', action='store_true', help='Export daily report automatically')
    parser.add_argument('--continuous', action='store_true', help='Run continuously (refresh every 30s)')
    args = parser.parse_args()
    
    monitor = DataMonitor()
    
    try:
        if args.continuous:
            print("🔄 Continuous monitoring mode - Press Ctrl+C to stop")
            import time
            while True:
                print(f"\n{'='*80}")
                print(f"📊 Data Monitor Dashboard - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"{'='*80}")
                
                # Display dashboard
                monitor.display_dashboard()
                
                # Check alerts
                monitor.check_alerts()
                
                if args.export:
                    monitor.export_daily_report()
                    print("✅ Daily report exported")
                
                print("\n⏳ Refreshing in 30 seconds... (Press Ctrl+C to stop)")
                time.sleep(30)
        else:
            # Single run mode
            monitor.display_dashboard()
            
            # Check alerts
            monitor.check_alerts()
            
            # Handle export
            if args.auto:
                if args.export:
                    monitor.export_daily_report()
                    print("✅ Daily report exported automatically")
            else:
                # Interactive mode
                export = input("\nExport daily report? (y/n): ").strip().lower()
                if export == 'y':
                    monitor.export_daily_report()
            
    except KeyboardInterrupt:
        if args.continuous:
            print("\n\n🛑 Monitoring stopped by user")
        else:
            print("\n\n🛑 Interrupted by user")
    finally:
        monitor.close()


if __name__ == "__main__":
    main()
