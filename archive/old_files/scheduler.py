#!/usr/bin/env python3
"""
Module: scheduler.py
Purpose: Schedule data collection every 5 minutes during market hours
Author: Trading Bot Developer
Created: 2025-06-12
Modified: 2025-06-12
"""

import time
import schedule
from datetime import datetime
import signal
import sys

from src.data_collector import DataCollector
from src.config import MARKET_OPEN, MARKET_CLOSE, MARKET_TIMEZONE, is_market_hours
from src.utils.logger import setup_logger

# Setup logger
logger = setup_logger(__name__, 'scheduler.log')

# Global collector instance
collector = None


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger.info("Received shutdown signal, cleaning up...")
    if collector:
        collector.close()
    sys.exit(0)


def run_collection():
    """Run data collection cycle"""
    if not is_market_hours():
        return
    
    try:
        logger.info("Starting scheduled collection")
        collector.run_collection_cycle()
    except Exception as e:
        logger.error(f"Collection failed: {e}")


def morning_startup():
    """Morning startup routine"""
    logger.info("="*60)
    logger.info("TRADING BOT STARTING - MORNING ROUTINE")
    logger.info("="*60)
    
    # Initialize collector if not already done
    global collector
    if not collector:
        collector = DataCollector()
    
    # Run system checks
    logger.info("Running system checks...")
    
    # Test API connectivity
    test_symbol = "RELIANCE"
    if collector.collect_and_store(test_symbol):
        logger.info("✅ API connectivity confirmed")
    else:
        logger.warning("⚠️  API connectivity issues detected")
    
    # Check database
    try:
        count = collector.db.conn.execute("SELECT COUNT(*) FROM price_data").fetchone()[0]
        logger.info(f"✅ Database operational - {count} records found")
    except Exception as e:
        logger.error(f"❌ Database error: {e}")
    
    logger.info("Morning startup complete")


def end_of_day():
    """End of day routine"""
    logger.info("="*60)
    logger.info("END OF DAY ROUTINE")
    logger.info("="*60)
    
    if collector:
        # Update daily stats
        collector.update_daily_stats()
        
        # Generate and log summary
        summary = collector.generate_summary()
        logger.info("Daily Summary:")
        for key, value in summary.items():
            logger.info(f"  {key}: {value}")
    
    logger.info("End of day routine complete")


def setup_schedule():
    """Setup the collection schedule"""
    # Morning startup
    schedule.every().day.at("09:00").do(morning_startup)
    
    # Regular collection every 5 minutes during market hours
    # We'll check every minute but only run during market hours
    schedule.every(5).minutes.do(run_collection)
    
    # End of day routine
    schedule.every().day.at("15:45").do(end_of_day)
    
    logger.info("Schedule configured:")
    logger.info("  - Morning startup: 09:00")
    logger.info("  - Data collection: Every 5 minutes during market hours")
    logger.info("  - End of day: 15:45")


def main():
    """Main scheduler loop"""
    global collector
    
    print("\n" + "="*60)
    print("TRADING BOT DATA COLLECTION SCHEDULER")
    print("="*60)
    print(f"Current time: {datetime.now()}")
    print(f"Market hours: {MARKET_OPEN} - {MARKET_CLOSE}")
    print("\nScheduler will run collection every 5 minutes during market hours")
    print("Press Ctrl+C to stop\n")
    
    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Initialize collector
        collector = DataCollector()
        logger.info("DataCollector initialized")
        
        # Setup schedule
        setup_schedule()
        
        # Run morning startup if between 9 AM and market close
        current_time = datetime.now().time()
        if current_time >= datetime.strptime("09:00", "%H:%M").time() and is_market_hours():
            logger.info("Running immediate startup as market is open")
            morning_startup()
        
        # Main loop
        logger.info("Scheduler started - waiting for scheduled tasks")
        
        while True:
            try:
                # Run pending scheduled jobs
                schedule.run_pending()
                
                # Display status every 30 minutes
                if datetime.now().minute % 30 == 0 and datetime.now().second < 1:
                    if is_market_hours():
                        print(f"[{datetime.now().strftime('%H:%M')}] Market OPEN - Collection active")
                    else:
                        print(f"[{datetime.now().strftime('%H:%M')}] Market CLOSED - Waiting...")
                
                # Sleep for 1 second
                time.sleep(1)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                time.sleep(60)  # Wait a minute before retrying
                
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        
    finally:
        if collector:
            collector.close()
        logger.info("Scheduler stopped")


if __name__ == "__main__":
    main()
