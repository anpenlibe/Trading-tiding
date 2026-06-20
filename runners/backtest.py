#!/usr/bin/env python3
"""Historical backtester.

Replays the live trading pipeline (AIBrain → SimpleRiskManager → PaperTrader)
over the local OHLCV database, sampling decision points at a configurable
interval, to test strategies under simulated real-time conditions.
"""

import os
import sys
import time
import argparse
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.platform.config import SYMBOLS, DB_PATH, INITIAL_CAPITAL, DEFAULT_DATA_INTERVAL, DEFAULT_PERIODS
from src.platform.types import MarketData
from src.marketdata.feed import DatabaseSource, Feed
from src.platform.logger import setup_logger

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
    interval: str = DEFAULT_DATA_INTERVAL  # which price_data interval to replay


def select_simulation_timestamps(all_timestamps, start_date, end_date, interval_minutes):
    """Pick the bars to simulate from a chronological list of timestamps.

    Selection rules:
    - Keep only bars whose date is within [start_date, end_date].
    - Prefer intraday bars at/after 10:00 (skip the pre-open / opening-auction
      noise). If the snapshot has no such bars in the window (a pure-daily
      snapshot only carries a midnight bar per day), relax that filter so the
      backtest still runs instead of silently simulating nothing.
    - Space kept bars at least `interval_minutes` apart using CUMULATIVE timing
      (gap measured from the last KEPT bar). This is robust across weekends and
      holidays — unlike exact modulo alignment, which silently dropped a sample
      whenever the N-days-later slot fell on a non-trading day and then never
      re-aligned to subsequent trading days.

    Pure function (no DB / no side effects) so it can be unit-tested directly.
    """
    start = pd.Timestamp(start_date).date()
    end = pd.Timestamp(end_date).date()

    def in_window(ts):
        return start <= ts.date() <= end

    candidates = sorted(ts for ts in all_timestamps if in_window(ts) and ts.hour >= 10)
    if not candidates:
        candidates = sorted(ts for ts in all_timestamps if in_window(ts))
        if candidates:
            logger.warning(
                "No intraday (>=10:00) bars in window; falling back to daily bars."
            )

    picked = []
    last = None
    for ts in candidates:
        if last is None or (ts - last).total_seconds() / 60 >= interval_minutes:
            picked.append(ts)
            last = ts
    return picked


def format_interval(minutes):
    """Human-readable rendering of a minute count (days / hours / minutes)."""
    if minutes % 1440 == 0:
        days = minutes // 1440
        return f"{days} day{'s' if days != 1 else ''}"
    if minutes % 60 == 0:
        hours = minutes // 60
        return f"{hours} hour{'s' if hours != 1 else ''}"
    return f"{minutes} minute{'s' if minutes != 1 else ''}"


class HistoricalSimulator:
    """Main historical simulation engine"""
    
    def __init__(self, config: SimulationConfig):
        self.config = config
        self.source = DatabaseSource(DB_PATH, config.interval)
        self.feed = None
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
        self.risk_manager = None
        self.paper_trader = None
        
        logger.info(f"Historical simulator initialized for {config.start_date} to {config.end_date}")
    
    def validate_config(self) -> bool:
        """Validate simulation configuration"""
        # Check if data exists for the period
        start_date, end_date = self.source.date_range(self.config.symbols)
        
        if not start_date or not end_date:
            logger.error("No historical data found in database")
            return False
        
        if self.config.start_date < start_date:
            logger.warning(f"Start date {self.config.start_date} is before available data {start_date}")
            self.config.start_date = start_date
        
        if self.config.end_date > end_date:
            logger.warning(f"End date {self.config.end_date} is after available data {end_date}")
            self.config.end_date = end_date

        # Guard against an inverted window (requested start later than the data's
        # end) so we never silently "simulate 0 time points".
        if self.config.start_date > self.config.end_date:
            logger.warning(
                f"Start {self.config.start_date} is after available end {self.config.end_date}; "
                f"clamping start to available start {start_date}"
            )
            self.config.start_date = start_date

        logger.info(f"Simulation period: {self.config.start_date} to {self.config.end_date}")
        return True
    
    def initialize_components(self):
        """Initialize AI brain and paper trader if enabled"""
        try:
            if self.config.enable_ai_brain:
                # Use AIBrain with multi-provider fallback (Groq → Gemini → rule-based).
                from src.decision.engine import AIBrain
                self.ai_brain = AIBrain()
                logger.info("AI Brain initialized (provider chain from coordinator)")
        except ImportError as e:
            logger.warning(f"AI Brain not available - continuing without AI decisions: {e}")
            self.config.enable_ai_brain = False
        
        try:
            if self.config.enable_ai_brain:  # Only need risk manager if using AI
                from src.risk.manager import SimpleRiskManager
                self.risk_manager = SimpleRiskManager()
                logger.info("Risk Manager initialized for simulation")
        except ImportError as e:
            logger.warning(f"Risk Manager not available: {e}")
        
        try:
            if self.config.enable_paper_trading:
                from src.execution.executor import PaperTrader
                self.paper_trader = PaperTrader(initial_capital=self.config.initial_capital)
                logger.info("Paper Trader initialized for simulation")
        except ImportError as e:
            logger.warning(f"Paper Trader not available - continuing without trade execution: {e}")
            self.config.enable_paper_trading = False
    
    def load_simulation_data(self):
        """Load historical data for simulation"""
        df = self.source.preload(self.config.symbols, self.config.start_date, self.config.end_date)
        if df.empty:
            raise ValueError("No data available for simulation period")
        
        self.feed = Feed(self.source)
        logger.info(f"Loaded {len(df)} data points for simulation")
    
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
        
        # Get unique timestamps in chronological order, then pick the bars to
        # simulate (in-window, intraday-preferred, spaced by the interval). The
        # selection logic lives in a pure, unit-tested helper.
        all_timestamps = self.source.all_timestamps()
        timestamps = select_simulation_timestamps(
            all_timestamps,
            self.config.start_date,
            self.config.end_date,
            self.config.simulation_interval_minutes,
        )

        self.simulation_stats['start_time'] = datetime.now()
        self.simulation_stats['total_ticks'] = len(timestamps)

        logger.info(f"Simulating {len(timestamps)} time points ({self.config.simulation_interval_minutes}-min intervals) from {timestamps[0] if timestamps else 'N/A'} to {timestamps[-1] if timestamps else 'N/A'}")
        logger.info(f"Filtered from {len(all_timestamps)} total data points to {len(timestamps)} simulation points")
        
        # Run simulation
        try:
            for i, timestamp in enumerate(timestamps):
                self.current_time = timestamp
                self.feed.set_time(timestamp)
                
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
            current_data = self.feed.current(symbol)
            if not current_data:
                skipped_symbols[symbol] = "No current data"
                continue

            # Get historical data for indicators
            historical_df = self.feed.history(symbol, 50)
            if len(historical_df) < 20:
                skipped_symbols[symbol] = f"Insufficient data ({len(historical_df)} periods)"
                continue

            # Calculate indicators
            indicators = self.feed.indicators(symbol)
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
                            logger.info(f"Skipping SELL for {symbol} - no position held")
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

    def _execute_simulated_trade(self, symbol: str, signal: Dict, current_price: float, timestamp: pd.Timestamp) -> Dict:
        """Execute a trade using the unified pipeline approach"""
        try:
            # The fill happens at the current market price; stamp it on the
            # signal so risk validation/sizing don't crash on a missing
            # entry_price (otherwise swallowed as a silent non-execution).
            if signal.get('entry_price') is None:
                signal['entry_price'] = current_price

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

        # Stamp timestamps if the run was interrupted before they were set
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
                data = self.feed.current(symbol)
                if data:
                    current_prices[symbol] = data.close
            
            # Update positions with final prices
            self.paper_trader.update_positions(current_prices)

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
        if self.source:
            self.source.close()



def prompt(text, default=""):
    """input() that returns ``default`` when stdin is exhausted (piped / CI),
    so non-interactive runs never crash with EOFError."""
    try:
        return input(text).strip()
    except EOFError:
        return default


def build_arg_parser():
    parser = argparse.ArgumentParser(description='Historical trading simulation')
    parser.add_argument('--auto', action='store_true', help='Run with defaults, no prompts')
    parser.add_argument('--days', type=int, default=3, help='Days to simulate, ending at the last available date (default: 3)')
    parser.add_argument('--symbols', nargs='+', help='Symbols to simulate (default: all configured)')
    parser.add_argument('--speed', type=float, default=5.0, help='Speed multiplier; >=100 skips the inter-tick sleep (default: 5.0)')
    parser.add_argument('--interval', choices=['1m', '5m', '15m', '30m', '1d'], default=DEFAULT_DATA_INTERVAL,
                        help=f'Candle interval to replay from the DB (default: {DEFAULT_DATA_INTERVAL})')
    parser.add_argument('--sim-interval', type=int, default=30, help='Minutes between decision points (default: 30)')
    parser.add_argument('--interval-days', type=int, help='Days between decision points (overrides --sim-interval; e.g. 3)')
    parser.add_argument('--start-date', type=str, help='Explicit window start (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, help='Explicit window end (YYYY-MM-DD)')
    return parser


def resolve_interval_minutes(args):
    """--interval-days is a convenience for day-scale steps and wins over
    --sim-interval (expressing 3 days as 4320 minutes is unintuitive)."""
    return args.interval_days * 1440 if args.interval_days else args.sim_interval


def resolve_window(args, available_start, available_end, interactive):
    """Decide ``(start_date, end_date, speed)`` for the run.

    Explicit --start-date/--end-date always win. A non-interactive run otherwise
    simulates the last --days days; an interactive run offers a menu. Relative
    windows anchor to the LAST available data date (not today) so they land
    inside the bundled snapshot.
    """
    data_end = pd.Timestamp(available_end)

    def lookback(days):
        return (data_end - timedelta(days=days)).strftime('%Y-%m-%d')

    if args.start_date and args.end_date:
        return args.start_date, args.end_date, args.speed

    if not interactive:
        return lookback(args.days), available_end, args.speed

    print("\nSimulation options:")
    print("1. Last 3 days (recommended)   3. Last month       5. All available data")
    print("2. Last week                   4. Custom range")
    choice = prompt("\nChoice (1-5): ", "1") or "1"

    if choice == "2":
        return lookback(7), available_end, 10.0
    if choice == "3":
        return lookback(30), available_end, 50.0
    if choice == "4":
        start = prompt(f"Start date (YYYY-MM-DD, earliest {available_start}): ", available_start) or available_start
        end = prompt(f"End date (YYYY-MM-DD, latest {available_end}): ", available_end) or available_end
        return start, end, float(prompt("Speed multiplier [10.0]: ", "10.0") or "10.0")
    if choice == "5":
        return available_start, available_end, 100.0
    if choice != "1":
        print("Invalid choice, using last 3 days")
    return lookback(3), available_end, 5.0


def prompt_interval_minutes():
    """Interactive interval menu; returns minutes between decision points."""
    presets = {"1": 30, "2": 15, "3": 5, "4": 1, "5": 60}
    print("\nSimulation interval options:")
    print("1. 30 minutes (default)   3. 5 minutes   5. 1 hour")
    print("2. 15 minutes             4. 1 minute    6. Custom")
    choice = prompt("Choose interval (1-6) [1]: ", "1") or "1"
    if choice in presets:
        return presets[choice]
    if choice == "6":
        try:
            minutes = int(prompt("Custom interval in minutes: ", "30"))
            if minutes > 0:
                return minutes
        except ValueError:
            pass
        print("Invalid interval, using 30 minutes")
    return 30


def main():
    args = build_arg_parser().parse_args()

    # A run is interactive only when nothing pins it down: no --auto, no explicit
    # window, and a real TTY on stdin. Otherwise we must never prompt -- doing so
    # previously crashed piped/CI runs with EOFError.
    explicit_dates = bool(args.start_date and args.end_date)
    interactive = not args.auto and not explicit_dates and sys.stdin.isatty()

    print("\U0001f570\ufe0f  HISTORICAL DATA SIMULATION")
    print("=" * 60)

    symbols = args.symbols or SYMBOLS
    provider = DatabaseSource(DB_PATH, args.interval)
    available_start, available_end = provider.date_range(symbols)
    provider.close()

    if not available_start:
        print("\u274c No historical data found. Run data collection first.")
        return

    print(f"\U0001f4ca Available data: {available_start} to {available_end}")
    print(f"\U0001f4c8 Symbols: {', '.join(symbols)}")

    start_date, end_date, speed = resolve_window(args, available_start, available_end, interactive)
    config = SimulationConfig(
        start_date=start_date,
        end_date=end_date,
        symbols=symbols,
        initial_capital=INITIAL_CAPITAL,
        speed_multiplier=speed,
        simulation_interval_minutes=resolve_interval_minutes(args),
        interval=args.interval,
    )

    if interactive:
        config.enable_ai_brain = prompt("\nEnable AI Brain? (y/n) [y]: ", "y").lower() != 'n'
        config.simulation_interval_minutes = prompt_interval_minutes()
        config.enable_paper_trading = prompt("Enable Paper Trading? (y/n) [y]: ", "y").lower() != 'n'
    elif explicit_dates:
        print(f"\n\U0001f916 Explicit window {start_date} \u2192 {end_date}")
    else:
        print(f"\n\U0001f916 Automated mode: last {args.days} days")

    print(f"\n\U0001f680 Simulating {config.start_date} \u2192 {config.end_date}")
    print(f"\u26a1 Speed: {config.speed_multiplier}x   "
          f"\u23f1\ufe0f  Interval: {format_interval(config.simulation_interval_minutes)}")
    print(f"\U0001f9e0 AI Brain: {'\u2705' if config.enable_ai_brain else '\u274c'}   "
          f"\U0001f4b0 Paper Trading: {'\u2705' if config.enable_paper_trading else '\u274c'}")

    if interactive:
        prompt("\nPress Enter to start...")

    simulator = HistoricalSimulator(config)
    try:
        simulator.run_simulation()
    finally:
        simulator.close()


if __name__ == "__main__":
    main()
