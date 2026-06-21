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
from src.platform.events import log_event

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
    general_pass_every: int = 1  # full general pass every N ticks; alert-driven special
                                 # passes run on the ticks between (1 = general every tick, no alerts)


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
        self.pipeline = None
        self.alert_manager = None
        
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

        # Shared decide->risk->execute pipeline (mode-agnostic; live will reuse it).
        if self.config.enable_ai_brain and self.ai_brain:
            from src.pipeline import TradingPipeline
            self.pipeline = TradingPipeline(self.ai_brain, self.risk_manager, self.paper_trader)
            # Alert manager drives the alert->special-pass loop between general passes.
            from src.alerts.manager import AlertManager
            self.alert_manager = AlertManager(self.config.symbols)
    
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

        # Register this run so the monitor can identify + liveness-check it.
        from src.platform.session import register_session
        register_session('backtest', symbols=self.config.symbols,
                         capital=INITIAL_CAPITAL, interval=self.config.interval,
                         sim_interval_min=self.config.simulation_interval_minutes,
                         general_every=self.config.general_pass_every,
                         total_ticks=len(timestamps))

        logger.info(f"Simulating {len(timestamps)} time points ({self.config.simulation_interval_minutes}-min intervals) from {timestamps[0] if timestamps else 'N/A'} to {timestamps[-1] if timestamps else 'N/A'}")
        logger.info(f"Filtered from {len(all_timestamps)} total data points to {len(timestamps)} simulation points")
        
        # Run simulation
        try:
            for i, timestamp in enumerate(timestamps):
                self.current_time = timestamp
                self.feed.set_time(timestamp)
                
                # Process each symbol at this timestamp
                self.process_timestamp(timestamp, i)
                
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
    
    def process_timestamp(self, timestamp: pd.Timestamp, tick_index: int = 0):
        """Gather bars for all symbols, then run the general pass (on cadence) or
        an alert-driven special pass (on the ticks between)."""

        # Collect data for all symbols
        portfolio_data = {}
        portfolio_indicators = {}
        current_prices = {}
        snapshots = {}  # {symbol: {close, volume, indicators}} for alert checks

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
            snapshots[symbol] = {'close': current_data.close, 'volume': current_data.volume, 'indicators': indicators}

        # Log diagnostic info
        if skipped_symbols:
            logger.warning(f"Skipped symbols at {timestamp}: {skipped_symbols}")
        logger.info(f"Processing {len(portfolio_data)} symbols: {list(portfolio_data.keys())}")

        # Skip if no valid data collected
        if not portfolio_data:
            return

        # General pass on its cadence; alert-driven special passes on the ticks between.
        if not (self.config.enable_ai_brain and self.pipeline):
            return

        is_general = tick_index % max(1, self.config.general_pass_every) == 0
        log_event('tick', sim_time=str(timestamp), symbols=len(portfolio_data),
                  pass_type='general' if is_general else 'alert')
        if is_general:
            self._run_general_pass(timestamp, portfolio_data, portfolio_indicators, current_prices)
        else:
            self._run_alert_pass(timestamp, portfolio_data, portfolio_indicators, current_prices, snapshots)

        # Mechanical stop/target floor: AFTER the AI/alert pass had first say, mark
        # to market and auto-close anything that reached its hard level. Record each
        # auto-close in the sim trade log and refresh alert levels so a closed
        # position stops waking us. Then snapshot account state for the monitor.
        for ex in self.pipeline.manage_positions(current_prices):
            self._record_trade(timestamp, ex['symbol'],
                               {'signal': 'SELL', 'confidence': 1.0,
                                'position_size': ex.get('quantity', 0),
                                'reasoning': f"Mechanical {ex.get('exit_reason')}"},
                               ex.get('price'), f"Auto-close: {ex.get('exit_reason')}")
            if self.alert_manager:
                self.alert_manager.refresh(self.paper_trader.get_positions())
        self.paper_trader.book.write_state()

    def _run_general_pass(self, timestamp, portfolio_data, portfolio_indicators, current_prices):
        """General pass: portfolio prompt over all symbols -> decisions; register the
        AI's alert_conditions so special passes can fire between cycles."""
        try:
            current_positions = self.paper_trader.get_positions() if self.paper_trader else {}
            position_symbols = [sym for sym, pos in current_positions.items() if pos.get('quantity', 0) > 0]
            account_info = self.paper_trader.get_account_info() if self.paper_trader else {}
            context = {
                'strategy': 'swing',
                'timestamp': timestamp,
                'simulation_interval': self.config.simulation_interval_minutes,
                'current_positions': position_symbols,
                'positions': current_positions,  # full per-symbol state for owned-stock context
                'account_info': account_info or {},
            }

            result = self.pipeline.run_decisions(
                portfolio_data, portfolio_indicators, current_prices, context
            )

            decisions = result['decisions']
            self.simulation_stats['ai_decisions'] += len(decisions)
            if self.alert_manager:
                self.alert_manager.update_from_general(decisions, current_positions)
            if result['market_analysis']:
                logger.info(f"Market Analysis at {timestamp}: {result['market_analysis'][:100]}...")
                log_event('analysis', sim_time=str(timestamp), text=result['market_analysis'][:300])

            for ex in result['executed']:
                self._record_trade(timestamp, ex['symbol'], ex['decision'], ex['price'],
                                   result['market_analysis'][:200])

            non_hold = len([d for d in decisions.values() if d.get('signal') != 'HOLD'])
            logger.info(f"Portfolio analysis completed: {len(decisions)} symbols analyzed, {non_hold} signals generated")
        except Exception as e:
            logger.error(f"Portfolio analysis error at {timestamp}: {e}")

    def _run_alert_pass(self, timestamp, portfolio_data, portfolio_indicators, current_prices, snapshots):
        """Between general passes: check alerts; each triggered symbol gets a fast
        single-symbol SPECIAL pass (gpt-oss) -> risk -> execute."""
        if not self.alert_manager:
            return
        triggered = self.alert_manager.evaluate(snapshots, now=timestamp)
        if not triggered:
            return
        logger.info(f"Alerts triggered at {timestamp}: {list(triggered)}")
        for symbol in triggered:
            if symbol not in portfolio_data:
                continue
            try:
                out = self.pipeline.run_special(
                    symbol, portfolio_data[symbol], portfolio_indicators[symbol], current_prices[symbol],
                    alert_context=triggered[symbol]
                )
                self.simulation_stats['ai_decisions'] += 1
                d = out['decision']
                logger.info(f"Special pass {symbol}: {d.get('signal')} (conf {d.get('confidence')})")
                ex = out.get('executed')
                if ex and ex.get('status') == 'EXECUTED':
                    self._record_trade(timestamp, symbol, d, current_prices[symbol],
                                       f"SPECIAL pass (alert on {symbol})")
                    # The book changed — re-derive stop/target/recheck alert levels
                    # so a just-opened position is managed (or a closed one stops
                    # waking us) without waiting for the next general pass.
                    self.alert_manager.refresh(self.paper_trader.get_positions())
            except Exception as e:
                logger.error(f"Special pass error for {symbol}: {e}")

    def _record_trade(self, timestamp, symbol, decision, price, market_analysis):
        """Append an executed trade to the run's trade log + bump the counter."""
        self.trades_executed.append({
            'timestamp': timestamp,
            'symbol': symbol,
            'action': decision['signal'],
            'price': price,
            'quantity': decision.get('position_size', 1),
            'reasoning': decision.get('reasoning', ''),
            'confidence': decision.get('confidence', 0),
            'stop_loss': decision.get('stop_loss'),
            'target': decision.get('target'),
            'market_analysis': market_analysis,
        })
        self.simulation_stats['trades_count'] += 1


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
    parser.add_argument('--general-every', type=int, default=1,
                        help='Run the general (all-symbols) pass every N ticks; alert-driven '
                             'single-symbol special passes run on the ticks between (default: 1 = no alerts)')
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
        general_pass_every=args.general_every,
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
