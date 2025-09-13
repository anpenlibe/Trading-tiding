#!/usr/bin/env python3
"""
Module: historical_simulator.py
Purpose: Simulate trading system on historical data for backtesting
Author: Trading Bot Developer
Created: 2025-06-16
Modified: 2025-06-30 - FIXED: Updated to use correct components and unified pipeline

This module allows you to run your trading system on historical data,
simulating real-time conditions for strategy testing and validation.

FIXES APPLIED:
- Changed from ai_brain_optimized to ai_brain (ClaudeAI)
- Changed from IndicatorCalculator to compute_indicators  
- Added risk manager integration
- Fixed method calls to match paper_trader API
- Updated to use claude_trader unified pipeline
"""

import os
import sys
import time
import sqlite3
import argparse
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from dataclasses import dataclass
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.config import SYMBOLS, DB_PATH, INITIAL_CAPITAL
from src.data_collector import DataCollector  # FIXED: No more IndicatorCalculator import
from src.core.indicator_engine import calculate_all_indicators  # FIXED: Use unified indicator engine
from src.interfaces import MarketData
from src.utils.logger import setup_logger

# Setup logger
logger = setup_logger(__name__, 'historical_simulation.log')


@dataclass
class SimulationConfig:
    """Configuration for historical simulation"""
    start_date: str  # YYYY-MM-DD format
    end_date: str    # YYYY-MM-DD format
    symbols: List[str]
    initial_capital: float
    speed_multiplier: float = 1.0  # 1.0 = real time, 10.0 = 10x faster
    simulation_interval_minutes: int = 30  # Minutes between simulation points
    enable_ai_brain: bool = True
    enable_paper_trading: bool = True


class HistoricalDataProvider:
    """Provides historical data in chronological order"""
    
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        logger.info("Historical data provider initialized")
    
    def get_data_range(self, symbols: List[str]) -> Tuple[str, str]:
        """Get the available date range for symbols"""
        placeholders = ','.join(['?' for _ in symbols])
        query = f'''
            SELECT 
                MIN(DATE(timestamp)) as start_date,
                MAX(DATE(timestamp)) as end_date,
                COUNT(*) as total_records
            FROM price_data 
            WHERE symbol IN ({placeholders})
        '''
        
        result = self.conn.execute(query, symbols).fetchone()
        logger.info(f"Available data: {result['start_date']} to {result['end_date']} ({result['total_records']} records)")
        return result['start_date'], result['end_date']
    
    def get_simulation_data(self, config: SimulationConfig) -> pd.DataFrame:
        """Get all data for simulation period, sorted chronologically"""
        placeholders = ','.join(['?' for _ in config.symbols])
        query = f'''
            SELECT 
                symbol, timestamp, open, high, low, close, volume, source
            FROM price_data 
            WHERE symbol IN ({placeholders})
                AND timestamp >= ? 
                AND timestamp <= ?
            ORDER BY timestamp ASC
        '''
     
        params = config.symbols + [config.start_date, config.end_date + ' 23:59:59']
        df = pd.read_sql_query(query, self.conn, params=params)
        
        if df.empty:
            logger.warning(f"No data found for period {config.start_date} to {config.end_date}")
            return df
        
        # Fix timestamp parsing
        df['timestamp'] = pd.to_datetime(df['timestamp'], format='ISO8601', utc=True)
        df['timestamp'] = df['timestamp'].dt.tz_localize(None)  # Remove timezone for consistency

        logger.info(f"Loaded {len(df)} records for simulation ({len(config.symbols)} symbols)")
        return df
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()


class SimulationDataCollector:
    """Simulates the DataCollector for historical data"""
    
    def __init__(self, historical_data: pd.DataFrame):
        self.historical_data = historical_data
        self.current_time = None
        # FIXED: No more IndicatorCalculator - using unified engine
        logger.info("Simulation data collector initialized")
    
    def set_current_time(self, timestamp: pd.Timestamp):
        """Set the current simulation time"""
        self.current_time = timestamp
    
    def get_current_data(self, symbol: str) -> Optional[MarketData]:
        """Get current data for a symbol at simulation time"""
        if self.current_time is None:
            return None
        
        # Get data at or before current time
        symbol_data = self.historical_data[
            (self.historical_data['symbol'] == symbol) & 
            (self.historical_data['timestamp'] <= self.current_time)
        ].tail(1)
        
        if symbol_data.empty:
            return None
        
        row = symbol_data.iloc[0]
        return MarketData(
            symbol=symbol,
            timestamp=row['timestamp'].to_pydatetime(),
            open=float(row['open']),
            high=float(row['high']),
            low=float(row['low']),
            close=float(row['close']),
            volume=int(row['volume']),
            source=f"simulation_{row['source']}"
        )
    
    def get_historical_data_for_indicators(self, symbol: str, periods: int = 200) -> pd.DataFrame:
        """Get historical data for indicator calculation"""
        if self.current_time is None:
            return pd.DataFrame()
        
        # Get data before current time
        symbol_data = self.historical_data[
            (self.historical_data['symbol'] == symbol) & 
            (self.historical_data['timestamp'] <= self.current_time)
        ].tail(periods)
        
        # FIXED: Check if DataFrame is empty and what columns exist
        if symbol_data.empty:
            return pd.DataFrame()

        # FIXED: Only select columns that actually exist
        required_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        available_columns = [col for col in required_columns if col in symbol_data.columns]
        
        if not available_columns:
            return pd.DataFrame()

        return symbol_data[['timestamp', 'open', 'high', 'low', 'close', 'volume']].copy()
    
    def calculate_indicators(self, symbol: str) -> Dict[str, float]:
        """Calculate indicators for current simulation time"""
        df = self.get_historical_data_for_indicators(symbol)
        if len(df) < 20:  # Minimum data for indicators
            return {}
        
        # FIXED: Use unified indicator engine
        return calculate_all_indicators(df)


class HistoricalSimulator:
    """Main historical simulation engine"""
    
    def __init__(self, config: SimulationConfig):
        self.config = config
        self.data_provider = HistoricalDataProvider(DB_PATH)
        self.simulation_data = None
        self.data_collector = None
        self.current_time = None
        self.trades_executed = []
        self.simulation_stats = {
            'start_time': None,
            'end_time': None,
            'total_ticks': 0,
            'trades_count': 0,
            'ai_decisions': 0
        }
        
        # Components (will be initialized as needed)
        self.ai_brain = None
        self.risk_manager = None  # FIXED: Added risk manager
        self.paper_trader = None
        
        logger.info(f"Historical simulator initialized for {config.start_date} to {config.end_date}")
    
    def validate_config(self) -> bool:
        """Validate simulation configuration"""
        # Check if data exists for the period
        start_date, end_date = self.data_provider.get_data_range(self.config.symbols)
        
        if not start_date or not end_date:
            logger.error("No historical data found in database")
            return False
        
        if self.config.start_date < start_date:
            logger.warning(f"Start date {self.config.start_date} is before available data {start_date}")
            self.config.start_date = start_date
        
        if self.config.end_date > end_date:
            logger.warning(f"End date {self.config.end_date} is after available data {end_date}")
            self.config.end_date = end_date
        
        logger.info(f"Simulation period: {self.config.start_date} to {self.config.end_date}")
        return True
    
    def initialize_components(self):
        """Initialize AI brain and paper trader if enabled"""
        try:
            if self.config.enable_ai_brain:
                # FIXED: Use correct ClaudeAI import
                from src.core.ai_brain import ClaudeAI
                self.ai_brain = ClaudeAI()
                logger.info("AI Brain (ClaudeAI) initialized for simulation")
        except ImportError as e:
            logger.warning(f"AI Brain not available - continuing without AI decisions: {e}")
            self.config.enable_ai_brain = False
        
        try:
            # FIXED: Add risk manager integration
            if self.config.enable_ai_brain:  # Only need risk manager if using AI
                from src.core.risk_manager import SimpleRiskManager
                self.risk_manager = SimpleRiskManager()
                logger.info("Risk Manager initialized for simulation")
        except ImportError as e:
            logger.warning(f"Risk Manager not available: {e}")
        
        try:
            if self.config.enable_paper_trading:
                from src.core.paper_trader import PaperTrader
                self.paper_trader = PaperTrader(initial_capital=self.config.initial_capital)
                logger.info("Paper Trader initialized for simulation")
        except ImportError as e:
            logger.warning(f"Paper Trader not available - continuing without trade execution: {e}")
            self.config.enable_paper_trading = False
    
    def load_simulation_data(self):
        """Load historical data for simulation"""
        self.simulation_data = self.data_provider.get_simulation_data(self.config)
        if self.simulation_data.empty:
            raise ValueError("No data available for simulation period")
        
        self.data_collector = SimulationDataCollector(self.simulation_data)
        logger.info(f"Loaded {len(self.simulation_data)} data points for simulation")
    
    def run_simulation(self):
        """Run the historical simulation"""
        logger.info("="*60)
        logger.info("STARTING HISTORICAL SIMULATION")
        logger.info("="*60)
        
        # Validate and prepare
        if not self.validate_config():
            logger.error("Configuration validation failed")
            return
        
        self.initialize_components()
        self.load_simulation_data()
        
        # Get unique timestamps in chronological order
        all_timestamps = sorted(self.simulation_data['timestamp'].unique())

        # Filter timestamps based on simulation_interval_minutes
        timestamps = []
        for ts in all_timestamps:
            if ts.minute % self.config.simulation_interval_minutes == 0:
                timestamps.append(ts)

        self.simulation_stats['start_time'] = datetime.now()
        self.simulation_stats['total_ticks'] = len(timestamps)

        logger.info(f"Simulating {len(timestamps)} time points ({self.config.simulation_interval_minutes}-min intervals) from {timestamps[0] if timestamps else 'N/A'} to {timestamps[-1] if timestamps else 'N/A'}")
        logger.info(f"Filtered from {len(all_timestamps)} total data points to {len(timestamps)} simulation points")
        
        # Run simulation
        try:
            for i, timestamp in enumerate(timestamps):
                self.current_time = timestamp
                self.data_collector.set_current_time(timestamp)
                
                # Process each symbol at this timestamp
                self.process_timestamp(timestamp)
                
                # Progress update
                if i % 100 == 0:
                    progress = (i / len(timestamps)) * 100
                    print(f"\rProgress: {progress:.1f}% ({i}/{len(timestamps)})", end='', flush=True)
                
                # Speed control
                if self.config.speed_multiplier < 100:  # Don't sleep if very fast
                    time.sleep(0.01 / self.config.speed_multiplier)
            
            print()  # New line after progress
            self.simulation_stats['end_time'] = datetime.now()
            self.finalize_simulation()
            
        except KeyboardInterrupt:
            logger.info("\nSimulation interrupted by user")
            self.finalize_simulation()
        except Exception as e:
            logger.error(f"Simulation error: {e}")
    
    def process_timestamp(self, timestamp: pd.Timestamp):
        """Process all symbols at a given timestamp using portfolio analysis"""

        # Collect data for all symbols
        portfolio_data = {}
        portfolio_indicators = {}
        current_prices = {}

        skipped_symbols = {}  # Track why symbols are skipped

        for symbol in self.config.symbols:
            # Get current data
            current_data = self.data_collector.get_current_data(symbol)
            if not current_data:
                skipped_symbols[symbol] = "No current data"
                continue

            # Get historical data for indicators
            historical_df = self.data_collector.get_historical_data_for_indicators(symbol, 50)
            if len(historical_df) < 20:
                skipped_symbols[symbol] = f"Insufficient data ({len(historical_df)} periods)"
                continue

            # Calculate indicators
            indicators = self.data_collector.calculate_indicators(symbol)
            if not indicators:
                skipped_symbols[symbol] = "No indicators calculated"
                continue

            # Add symbol column for analysis
            historical_df['symbol'] = symbol

            # Store data for portfolio analysis
            portfolio_data[symbol] = historical_df
            portfolio_indicators[symbol] = indicators
            current_prices[symbol] = current_data.close

        # Log diagnostic info
        if skipped_symbols:
            logger.warning(f"Skipped symbols at {timestamp}: {skipped_symbols}")
        logger.info(f"Processing {len(portfolio_data)} symbols: {list(portfolio_data.keys())}")

        # Skip if no valid data collected
        if not portfolio_data:
            return

        # Make single portfolio AI decision
        if self.config.enable_ai_brain and self.ai_brain:
            try:
                # Get current portfolio positions
                current_positions = self.paper_trader.get_positions() if self.paper_trader else []
                position_symbols = [symbol for symbol, pos_data in current_positions.items() if pos_data.get('quantity', 0) > 0]

                # Get account info safely
                account_info = {}
                if self.paper_trader:
                    try:
                        account_info = self.paper_trader.get_account_info() or {}
                    except Exception as e:
                        logger.debug(f"Could not get account info: {e}")
                        account_info = {}

                # Create context for portfolio analysis
                context = {
                    'strategy': 'swing',
                    'timestamp': timestamp,
                    'simulation_interval': self.config.simulation_interval_minutes,
                    'current_positions': position_symbols,
                    'account_info': account_info
                }

                # Portfolio analysis with intelligent fallback for position protection
                portfolio_result = self.ai_brain.analyze_portfolio_with_intelligent_fallback(
                    portfolio_data, portfolio_indicators, context
                )

                # Update statistics
                num_decisions = len(portfolio_result.get('decisions', {}))
                self.simulation_stats['ai_decisions'] += num_decisions

                # Log market analysis and fallback status
                market_analysis = portfolio_result.get('market_analysis', '')
                if market_analysis:
                    logger.info(f"Market Analysis at {timestamp}: {market_analysis[:100]}...")

                # Log intelligent fallback status if used
                fallback_type = portfolio_result.get('fallback_type')
                if fallback_type:
                    critical_analyzed = portfolio_result.get('critical_symbols_analyzed', 0)
                    owned_protected = portfolio_result.get('owned_positions_protected', 0)
                    logger.warning(f"Intelligent fallback activated: {fallback_type}, protected {owned_protected} positions with {critical_analyzed} individual analyses")

                # Process individual decisions
                for symbol, decision in portfolio_result.get('decisions', {}).items():
                    if symbol not in current_prices:
                        continue

                    signal_type = decision.get('signal')

                    # Check if we can actually execute this trade
                    if signal_type == "SELL":
                        if not self.paper_trader.has_position(symbol):
                            logger.debug(f"Skipping SELL for {symbol} - no position held")
                            continue

                    # Execute trade if signal is not HOLD
                    if (self.config.enable_paper_trading and
                        self.paper_trader and
                        signal_type != "HOLD"):

                        trade_result = self._execute_simulated_trade(
                            symbol, decision, current_prices[symbol], timestamp
                        )

                        if trade_result.get('status') == 'EXECUTED':
                            self.trades_executed.append({
                                'timestamp': timestamp,
                                'symbol': symbol,
                                'action': decision['signal'],
                                'price': current_prices[symbol],
                                'quantity': decision.get('position_size', 1),
                                'reasoning': decision.get('reasoning', ''),
                                'confidence': decision.get('confidence', 0),
                                'stop_loss': decision.get('stop_loss'),
                                'target': decision.get('target'),
                                'market_analysis': market_analysis[:200]  # Store brief market context
                            })
                            self.simulation_stats['trades_count'] += 1

                logger.info(f"Portfolio analysis completed: {num_decisions} symbols analyzed, {len([d for d in portfolio_result.get('decisions', {}).values() if d.get('signal') != 'HOLD'])} signals generated")

            except Exception as e:
                logger.error(f"Portfolio analysis error at {timestamp}: {e}")
                # Fallback to individual analysis is currently disabled for testing.
                # This can be re-enabled for live trading to ensure robustness.
                # self._fallback_individual_analysis(portfolio_data, portfolio_indicators, current_prices, timestamp)

    def _fallback_individual_analysis(self, portfolio_data, portfolio_indicators, current_prices, timestamp):
        """Fallback to individual symbol analysis if portfolio analysis fails"""
        logger.warning("Falling back to individual symbol analysis")

        for symbol in portfolio_data.keys():
            try:
                if symbol in portfolio_indicators and symbol in current_prices:
                    # Use single-symbol analysis as fallback
                    signal = self.ai_brain.analyze(portfolio_data[symbol], portfolio_indicators[symbol])
                    self.simulation_stats['ai_decisions'] += 1

                    # Execute trade if needed
                    if (self.config.enable_paper_trading and
                        self.paper_trader and
                        signal.get('signal') != "HOLD"):

                        trade_result = self._execute_simulated_trade(
                            symbol, signal, current_prices[symbol], timestamp
                        )

                        if trade_result.get('status') == 'EXECUTED':
                            self.trades_executed.append({
                                'timestamp': timestamp,
                                'symbol': symbol,
                                'action': signal['signal'],
                                'price': current_prices[symbol],
                                'quantity': signal.get('position_size', 1),
                                'reasoning': signal.get('reasoning', ''),
                                'confidence': signal.get('confidence', 0),
                                'stop_loss': signal.get('stop_loss'),
                                'target': signal.get('target')
                            })
                            self.simulation_stats['trades_count'] += 1

            except Exception as e:
                logger.debug(f"Fallback analysis error for {symbol}: {e}")
    
    def _execute_simulated_trade(self, symbol: str, signal: Dict, current_price: float, timestamp: pd.Timestamp) -> Dict:
        """Execute a trade using the unified pipeline approach"""
        try:
            # Validate trade with risk manager if available
            if self.risk_manager:
                # Get current account info
                account_info = self.paper_trader.get_account_info()
                signal['available_capital'] = account_info['available_capital']
                
                # Validate trade
                current_positions = self.paper_trader.get_positions()
                is_valid, rejection_reason = self.risk_manager.validate_trade(signal, current_positions)
                
                if not is_valid:
                    return {
                        'status': 'REJECTED',
                        'reason': rejection_reason
                    }
                
                # Calculate risk parameters
                risk_params = self.risk_manager.calculate_risk_parameters(
                    symbol=symbol,
                    signal_type=signal['signal'],
                    entry_price=current_price,
                    capital=account_info['available_capital'],
                    stop_loss=signal.get('stop_loss'),
                    target=signal.get('target')
                )
                
                # Update signal with risk calculations
                signal.update({
                    'position_size': risk_params.position_size,
                    'stop_loss': risk_params.stop_loss,
                    'target': risk_params.target,
                    'entry_price': risk_params.entry_price,
                    'risk_amount': risk_params.risk_amount
                })
            
            # Add symbol to the signal dictionary before execution
            signal['symbol'] = symbol
            
            # FIXED: Use correct execute_trade method
            return self.paper_trader.execute_trade(signal, current_price)
            
        except Exception as e:
            logger.debug(f"Trade execution error for {symbol}: {e}")
            return {
                'status': 'ERROR',
                'reason': str(e)
            }
    
    def finalize_simulation(self):
        """Generate simulation summary"""
        
        logger.info("="*60)
        logger.info("SIMULATION COMPLETE")
        logger.info("="*60)

        # FIXED: Handle None end_time safely
        if self.simulation_stats['end_time'] is None:
            self.simulation_stats['end_time'] = datetime.now()
    
        if self.simulation_stats['start_time'] is None:
            self.simulation_stats['start_time'] = datetime.now()
    
        # Calculate duration safely
        try:
            duration = (self.simulation_stats['end_time'] - self.simulation_stats['start_time']).total_seconds()
        except (TypeError, AttributeError):
            duration = 0

        logger.info(f"Duration: {duration:.1f} seconds")
        logger.info(f"Time points processed: {self.simulation_stats['total_ticks']}")
        logger.info(f"AI decisions made: {self.simulation_stats['ai_decisions']}")
        logger.info(f"Trades executed: {self.simulation_stats['trades_count']}")
        
        if self.config.enable_paper_trading and self.paper_trader:
            # Get current prices for final P&L calculation
            current_prices = {}
            for symbol in self.config.symbols:
                data = self.data_collector.get_current_data(symbol)
                if data:
                    current_prices[symbol] = data.close
            
            # Update positions with final prices
            self.paper_trader.update_positions(current_prices)
            
            # FIXED: Use correct method name
            account_info = self.paper_trader.get_account_info()
            logger.info(f"Final Capital: ₹{account_info['current_capital']:.2f}")
            logger.info(f"Total Return: {account_info['total_return']:+.2f}%")
            logger.info(f"Win Rate: {account_info['win_rate']:.1f}%")
            logger.info(f"Total Trades: {account_info['total_trades']}")
            logger.info(f"Open Positions: {account_info['open_positions']}")
            
            # Generate performance report
            try:
                performance_report = self.paper_trader.generate_performance_report()
                logger.info(f"Max Drawdown: {performance_report['max_drawdown']:.2f}%")
                logger.info(f"Profit Factor: {performance_report.get('profit_factor', 'N/A')}")
            except Exception as e:
                logger.debug(f"Error generating performance report: {e}")
        
        # Save trade log
        if self.trades_executed:
            import json
            log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'logs')
            os.makedirs(log_dir, exist_ok=True)
            
            log_file = os.path.join(log_dir, f"simulation_trades_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            
            with open(log_file, 'w') as f:
                json.dump(self.trades_executed, f, indent=2, default=str)
            logger.info(f"Trade log saved to: {log_file}")
        
        return {
            'duration': duration,
            'ai_decisions': self.simulation_stats['ai_decisions'],
            'trades_executed': self.simulation_stats['trades_count'],
            'final_performance': account_info if self.paper_trader else None
        }
    
    def close(self):
        """Clean up resources"""
        if self.data_provider:
            self.data_provider.close()


def create_default_config() -> SimulationConfig:
    """Create a default simulation configuration"""
    # Use last 7 days of data if available
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    return SimulationConfig(
        start_date=start_date,
        end_date=end_date,
        symbols=SYMBOLS[:3],  # Test with first 3 symbols
        initial_capital=INITIAL_CAPITAL,
        speed_multiplier=10.0,  # 10x speed
        enable_ai_brain=True,
        enable_paper_trading=True
    )


def main():
    """Main function for running historical simulation"""
    parser = argparse.ArgumentParser(description='Historical trading simulation')
    parser.add_argument('--auto', action='store_true', help='Run in automated mode with defaults')
    parser.add_argument('--days', type=int, default=3, help='Number of days to simulate (default: 3)')
    parser.add_argument('--symbols', nargs='+', help='Symbols to simulate (default: all configured)')
    parser.add_argument('--speed', type=float, default=5.0, help='Simulation speed multiplier (default: 5.0)')
    parser.add_argument('--sim-interval', type=int, default=30, help='Simulation interval in minutes (default: 30)')
    parser.add_argument('--start-date', type=str, help='Start date for simulation (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, help='End date for simulation (YYYY-MM-DD)')
    args = parser.parse_args()
    
    print("🕰️  HISTORICAL DATA SIMULATION")
    print("="*60)
    
    # Use specified symbols or default to all configured
    symbols = args.symbols if args.symbols else SYMBOLS
    
    # Check available data
    provider = HistoricalDataProvider(DB_PATH)
    start_date, end_date = provider.get_data_range(symbols)
    provider.close()
    
    if not start_date:
        print("❌ No historical data found. Please run data collection first.")
        return
    
    print(f"📊 Available data: {start_date} to {end_date}")
    print(f"📈 Symbols: {', '.join(symbols)}")
    
    if args.auto:
        # Automated mode - use command line args
        choice = "1"  # Default to last N days
        print(f"\n🤖 Automated mode: Simulating last {args.days} days")
    else:
        # Interactive mode
        print("\nSimulation options:")
        print("1. Last 3 days (recommended)")
        print("2. Last week")
        print("3. Last month")
        print("4. Custom date range")
        print("5. Use all available data")
        
        choice = input("\nChoice (1-5): ").strip()
    
    config = create_default_config()
    config.symbols = symbols  # Use the selected symbols
    config.simulation_interval_minutes = args.sim_interval
    
    if args.start_date and args.end_date:
        config.start_date = args.start_date
        config.end_date = args.end_date
        config.speed_multiplier = args.speed
    elif choice == "1":
        days_to_simulate = args.days if args.auto else 3
        config.start_date = (datetime.now() - timedelta(days=days_to_simulate)).strftime('%Y-%m-%d')
        config.speed_multiplier = args.speed if args.auto else 5.0
    elif choice == "2":
        config.start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        config.speed_multiplier = 10.0
    elif choice == "3":
        config.start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        config.speed_multiplier = 50.0
    elif choice == "4":
        if args.auto:
            # Use reasonable defaults for automated mode
            config.start_date = (datetime.now() - timedelta(days=args.days)).strftime('%Y-%m-%d')
            config.end_date = datetime.now().strftime('%Y-%m-%d')
            config.speed_multiplier = args.speed
        else:
            config.start_date = input(f"Start date (YYYY-MM-DD, earliest: {start_date}): ").strip()
            config.end_date = input(f"End date (YYYY-MM-DD, latest: {end_date}): ").strip()
            config.speed_multiplier = float(input("Speed multiplier (1.0 = real time, 10.0 = 10x faster): ") or "10.0")
    elif choice == "5":
        config.start_date = start_date
        config.end_date = end_date
        config.speed_multiplier = 100.0
    else:
        print("Invalid choice, using default (last 3 days)")
    
    # Configure components
    if args.auto:
        # Automated mode - use defaults
        config.enable_ai_brain = True
        config.enable_paper_trading = True
        print(f"\n🤖 Automated configuration: AI enabled, Paper trading enabled")
    else:
        # Interactive mode
        if input(f"\nEnable AI Brain? (y/n) [y]: ").strip().lower() != 'n':
            config.enable_ai_brain = True
        else:
            config.enable_ai_brain = False
        
        if input(f"Enable Paper Trading? (y/n) [y]: ").strip().lower() != 'n':
            config.enable_paper_trading = True
        else:
            config.enable_paper_trading = False
    
    print(f"\n🚀 Starting simulation from {config.start_date} to {config.end_date}")
    print(f"⚡ Speed: {config.speed_multiplier}x")
    print(f"⏱️  Simulation Interval: {config.simulation_interval_minutes} minutes")
    print(f"🧠 AI Brain: {'✅' if config.enable_ai_brain else '❌'}")
    print(f"💰 Paper Trading: {'✅' if config.enable_paper_trading else '❌'}")
    print("\nPress Ctrl+C to stop the simulation at any time")
    
    if not args.auto:
        input("Press Enter to start...")
    else:
        print("🚀 Starting automated simulation...")
    
    # Run simulation
    simulator = HistoricalSimulator(config)
    try:
        simulator.run_simulation()
    finally:
        simulator.close()


if __name__ == "__main__":
    main()
