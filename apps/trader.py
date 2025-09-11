"""
Module: claude_trader.py
Purpose: Main Claude-driven trading system orchestrator
Author: Trading Bot Developer
Created: 2025-06-30
Modified: 2025-06-30

This module integrates all components into a cohesive Claude-driven trading system:
- AI Brain (Claude) for trading decisions
- Risk Manager for position sizing and safety
- Paper Trader for execution and tracking
- Data Collector for market data and indicators

Features:
- Automated trading cycles
- Real-time position management
- Performance tracking and reporting
- Risk management integration
- Error handling and logging
"""

import os
import sys
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import asdict

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.ai_brain import ClaudeAI
from src.core.risk_manager import SimpleRiskManager  
from src.core.paper_trader import PaperTrader
from src.data_collector import DataCollector
from src.core.indicator_engine import calculate_all_indicators
from src.data.config import SYMBOLS, INITIAL_CAPITAL, is_market_hours, ENABLE_ALERTS, PRICE_ALERT_THRESHOLD
from src.utils.logger import setup_logger
from src.exceptions import TradingSystemError, DataCollectionError, AIAnalysisError
from src.alerts.alert_engine import AlertEngine, AlertType
from src.alerts.rules import PriceCrossRule, RSIExtremeRule, VolumeSpikRule, MACDCrossRule

# Initialize logger
logger = setup_logger(__name__, 'claude_trader.log')


class ClaudeTrader:
    """
    Main Claude-driven trading system.
    
    Orchestrates all components to create an AI-powered trading bot
    that can analyze markets, manage risk, and execute trades.
    """
    
    def __init__(self, initial_capital: float = INITIAL_CAPITAL, test_mode: bool = False):
        """
        Initialize the Claude trading system.
        
        Args:
            initial_capital: Starting capital for trading
            test_mode: If True, uses mock data and additional logging
        """
        self.initial_capital = initial_capital
        self.test_mode = test_mode
        self.start_time = datetime.now()
        
        logger.info(f"Initializing Claude Trader with ₹{initial_capital} capital")
        logger.info(f"Test mode: {test_mode}")
        
        # Initialize components
        try:
            self.ai_brain = ClaudeAI()
            self.risk_manager = SimpleRiskManager()
            self.paper_trader = PaperTrader(initial_capital)
            self.data_collector = DataCollector()
            
            # Initialize alert engine if enabled
            if ENABLE_ALERTS:
                self.alert_engine = AlertEngine()
                self.symbols = SYMBOLS  # Store symbols for alert setup
                self._setup_alerts()
                logger.info("Alert engine initialized")
            else:
                self.alert_engine = None
                logger.info("Alert engine disabled")
            
            logger.info("All components initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize components: {e}")
            raise
        
        # Performance tracking
        self.trading_cycles = 0
        self.total_signals = 0
        self.executed_trades = 0
        self.skipped_signals = 0
        self.error_count = 0
        
        # Decision history for analysis
        self.decision_history = []
        
        logger.info("Claude Trader initialization complete")
    
    def _setup_alerts(self):
        """Configure alert rules."""
        if not self.alert_engine:
            return
            
        for symbol in self.symbols:
            # Price alerts
            recent_data = self.data_collector.get_recent_data(symbol, 1)
            if not recent_data.empty:
                current_price = recent_data.iloc[-1]['close']
                
                # Alert on 2% moves
                self.alert_engine.add_rule(
                    PriceCrossRule(symbol, current_price * (1 + PRICE_ALERT_THRESHOLD), "above")
                )
                self.alert_engine.add_rule(
                    PriceCrossRule(symbol, current_price * (1 - PRICE_ALERT_THRESHOLD), "below")
                )
            
            # RSI extremes
            self.alert_engine.add_rule(RSIExtremeRule(symbol))
            
            # Volume spikes
            self.alert_engine.add_rule(VolumeSpikRule(symbol, 2.0))
            
            # MACD crossovers
            self.alert_engine.add_rule(MACDCrossRule(symbol, "bullish"))
            self.alert_engine.add_rule(MACDCrossRule(symbol, "bearish"))
        
        # Register callbacks
        self.alert_engine.register_callback(
            AlertType.RSI_EXTREME, 
            self._handle_rsi_alert
        )
        self.alert_engine.register_callback(
            AlertType.PRICE_CROSS,
            self._handle_price_alert
        )
        self.alert_engine.register_callback(
            AlertType.VOLUME_SPIKE,
            self._handle_volume_alert
        )
        self.alert_engine.register_callback(
            AlertType.MACD_CROSS,
            self._handle_macd_alert
        )
    
    def _handle_rsi_alert(self, alert):
        """Handle RSI extreme alerts."""
        logger.info(f"RSI Alert: {alert.symbol} RSI={alert.current_value:.1f}")
        
        # Trigger immediate analysis
        self._analyze_and_trade(alert.symbol)
    
    def _handle_price_alert(self, alert):
        """Handle price cross alerts."""
        logger.info(f"Price Alert: {alert.symbol} crossed {alert.threshold:.2f}")
        
        # Trigger immediate analysis
        self._analyze_and_trade(alert.symbol)
    
    def _handle_volume_alert(self, alert):
        """Handle volume spike alerts."""
        logger.info(f"Volume Alert: {alert.symbol} volume spike {alert.current_value:.0f}")
        
        # Trigger immediate analysis for volume spikes
        self._analyze_and_trade(alert.symbol)
    
    def _handle_macd_alert(self, alert):
        """Handle MACD crossover alerts."""
        direction = alert.metadata.get('crossover_direction', 'unknown')
        logger.info(f"MACD Alert: {alert.symbol} {direction} crossover")
        
        # Trigger immediate analysis
        self._analyze_and_trade(alert.symbol)
    
    def _analyze_and_trade(self, symbol: str):
        """Analyze symbol and execute trade if conditions met."""
        try:
            # Collect data
            if not self._collect_data_safely(symbol):
                return
            
            # Generate signal
            signal = self._generate_signal_safely(symbol)
            if not signal:
                return
            
            # Execute trade if not HOLD
            if signal['signal'] != 'HOLD':
                self._execute_trade_safely(symbol, signal)
                
        except Exception as e:
            logger.error(f"Error in alert-triggered analysis for {symbol}: {e}")
    
    def _get_latest_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get latest data for alert checking."""
        try:
            df = self.data_collector.get_recent_data(symbol, 1)
            if df.empty:
                return None
            
            latest = df.iloc[-1]
            indicators = calculate_all_indicators(df)
            
            return {
                'symbol': symbol,
                'open': latest['open'],
                'high': latest['high'],
                'low': latest['low'],
                'close': latest['close'],
                'volume': latest['volume'],
                'indicators': indicators
            }
        except Exception as e:
            logger.error(f"Error getting latest data for {symbol}: {e}")
            return None
    
    def run_alert_mode(self):
        """Run in alert-driven mode (more efficient)."""
        if not self.alert_engine:
            logger.error("Alert engine not initialized")
            return
            
        logger.info("Starting alert-driven trading mode")
        
        try:
            while True:
                try:
                    # Quick data check (lightweight)
                    for symbol in self.symbols:
                        data = self._get_latest_data(symbol)
                        if data:
                            # Check alerts
                            triggered = self.alert_engine.check_conditions(data)
                            
                            if triggered:
                                logger.info(f"{len(triggered)} alerts triggered for {symbol}")
                    
                    # Sleep briefly (1 minute instead of 5)
                    time.sleep(60)
                    
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    logger.error(f"Alert mode error: {e}")
                    time.sleep(60)  # Continue after error
                    
        except Exception as e:
            logger.error(f"Critical error in alert mode: {e}")
        finally:
            logger.info("Alert-driven trading mode stopped")

    def run_trading_cycle(self) -> Dict[str, Any]:
        """
        Execute one trading cycle with error recovery.
        
        Process:
        1. Collect market data for all symbols
        2. Calculate technical indicators  
        3. Get Claude's analysis for each symbol
        4. Execute trades based on AI decisions
        5. Update positions and track performance
        
        Returns:
            Summary of trading cycle results
        """
        try:
            start_time = time.time()
            logger.info("=" * 60)
            logger.info("Starting trading cycle")
            
            cycle_summary = {
                'timestamp': datetime.now().isoformat(),
                'symbols_processed': 0,
                'signals_generated': 0,
                'trades_executed': 0,
                'errors': [],
                'cycle_duration': 0.0
            }
            
            for symbol in SYMBOLS:
                try:
                    # Collect data with error handling
                    if not self._collect_data_safely(symbol):
                        cycle_summary['errors'].append(f"Data collection failed: {symbol}")
                        continue
                    
                    # Generate signal with error handling
                    signal = self._generate_signal_safely(symbol)
                    if not signal:
                        continue
                    
                    cycle_summary['signals_generated'] += 1
                    
                    # Execute trade with error handling
                    if signal['signal'] != 'HOLD':
                        if self._execute_trade_safely(symbol, signal):
                            cycle_summary['trades_executed'] += 1
                    
                    cycle_summary['symbols_processed'] += 1
                    
                except Exception as e:
                    logger.error(f"Error processing {symbol}: {e}")
                    cycle_summary['errors'].append(f"{symbol}: {str(e)}")
                    continue
            
            # Update tracking
            self.trading_cycles += 1
            cycle_summary['cycle_duration'] = time.time() - start_time
            
            # Log cycle summary
            logger.info(f"Cycle complete: {cycle_summary['symbols_processed']} symbols, "
                       f"{cycle_summary['signals_generated']} signals, "
                       f"{cycle_summary['trades_executed']} trades in {cycle_summary['cycle_duration']:.1f}s")
            
            if cycle_summary['errors']:
                logger.warning(f"Errors encountered: {len(cycle_summary['errors'])}")
                for error in cycle_summary['errors'][:5]:  # Log first 5 errors
                    logger.warning(f"  - {error}")
            
            return cycle_summary
            
        except Exception as e:
            logger.error(f"Critical error in trading cycle: {e}")
            return None

    def _collect_data_safely(self, symbol: str) -> bool:
        """Collect data with error handling."""
        try:
            return self.data_collector.collect_and_store(symbol)
        except Exception as e:
            logger.error(f"Failed to collect data for {symbol}: {e}")
            return False

    def _generate_signal_safely(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Generate signal with error handling."""
        try:
            # Get recent data
            df = self.data_collector.get_recent_data(symbol)
            if df is None or df.empty:
                return None
            
            # Compute indicators
            indicators = calculate_all_indicators(df)
            
            # Add symbol for AI analysis
            df['symbol'] = symbol
            
            # Get AI analysis
            return self.ai_brain.analyze(df, indicators)
            
        except Exception as e:
            logger.error(f"Failed to generate signal for {symbol}: {e}")
            return None

    def _execute_trade_safely(self, symbol: str, signal: Dict[str, Any]) -> bool:
        """Execute trade with error handling."""
        try:
            # Get current price
            df = self.data_collector.get_recent_data(symbol, 1)
            if df.empty:
                return False
            
            current_price = df.iloc[-1]['close']
            
            # Get account info
            account_info = self.paper_trader.get_account_info()
            signal['available_capital'] = account_info['available_capital']
            
            # Validate with risk manager
            current_positions = self.paper_trader.get_positions()
            is_valid, rejection_reason = self.risk_manager.validate_trade(signal, current_positions)
            
            if not is_valid:
                logger.info(f"Trade rejected for {symbol}: {rejection_reason}")
                return False
            
            # Execute trade
            result = self.paper_trader.execute_trade(signal, current_price)
            
            return result.get('success', False) if isinstance(result, dict) else False
            
        except Exception as e:
            logger.error(f"Failed to execute trade for {symbol}: {e}")
            return False
    
    def _get_market_data_and_indicators(self, symbol: str) -> tuple[Optional[Any], Optional[Dict]]:
        """
        Get market data and calculated indicators for a symbol.
        
        Args:
            symbol: Stock symbol to analyze
            
        Returns:
            Tuple of (market_data_df, indicators_dict)
        """
        try:
            # Get recent historical data for analysis
            market_data = self.data_collector.get_recent_data(symbol, periods=50)
            
            if market_data.empty:
                logger.warning(f"No historical data available for {symbol}")
                return None, None
            
            # Add symbol column for AI analysis
            market_data['symbol'] = symbol
            
            # Calculate indicators
            indicators = calculate_all_indicators(market_data)
            
            logger.debug(f"Retrieved data for {symbol}: {len(market_data)} periods, {len(indicators)} indicators")
            
            return market_data, indicators
            
        except Exception as e:
            logger.error(f"Error getting market data for {symbol}: {e}")
            return None, None
    
    def _get_claude_decision(self, symbol: str, market_data: Any, indicators: Dict[str, float]) -> Optional[Dict[str, Any]]:
        """
        Get trading decision from Claude AI.
        
        Args:
            symbol: Stock symbol
            market_data: Historical price data
            indicators: Technical indicators
            
        Returns:
            Trading signal dict or None if error
        """
        try:
            # Get Claude's analysis
            signal = self.ai_brain.analyze(market_data, indicators)
            
            # Add symbol to signal for execution
            signal['symbol'] = symbol
            
            logger.debug(f"Claude decision for {symbol}: {signal['signal']} (confidence: {signal.get('confidence', 0):.2f})")
            
            return signal
            
        except Exception as e:
            logger.error(f"Error getting Claude decision for {symbol}: {e}")
            return None
    
    def _execute_signal(self, symbol: str, signal: Dict[str, Any], current_price: float) -> Dict[str, Any]:
        """
        Execute trading signal through paper trader.
        
        Args:
            symbol: Stock symbol
            signal: Trading signal from Claude
            current_price: Current market price
            
        Returns:
            Execution result
        """
        try:
            # Skip HOLD signals
            if signal.get('signal') == 'HOLD':
                return {
                    'status': 'SKIPPED',
                    'reason': 'HOLD signal - no action taken'
                }
            
            # Get current account info for risk validation
            account_info = self.paper_trader.get_account_info()
            signal['available_capital'] = account_info['available_capital']
            
            # Validate trade with risk manager
            current_positions = self.paper_trader.get_positions()
            is_valid, rejection_reason = self.risk_manager.validate_trade(signal, current_positions)
            
            if not is_valid:
                logger.info(f"Trade rejected for {symbol}: {rejection_reason}")
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
            
            # Update signal with risk manager calculations
            signal.update({
                'position_size': risk_params.position_size,
                'stop_loss': risk_params.stop_loss,
                'target': risk_params.target,
                'entry_price': risk_params.entry_price,
                'risk_amount': risk_params.risk_amount
            })
            
            # Execute through paper trader
            execution_result = self.paper_trader.execute_trade(signal, current_price)
            
            logger.info(f"Execution result for {symbol}: {execution_result.get('status')}")
            
            return execution_result
            
        except Exception as e:
            logger.error(f"Error executing signal for {symbol}: {e}")
            return {
                'status': 'ERROR',
                'reason': str(e)
            }
    
    def run_continuous_trading(self, max_cycles: int = 100, cycle_interval: int = 300):
        """
        Run continuous trading with comprehensive error recovery.
        
        Args:
            max_cycles: Maximum number of cycles to run
            cycle_interval: Seconds between cycles (default 5 minutes)
        """
        logger.info(f"Starting continuous trading: {max_cycles} cycles, {cycle_interval}s intervals")
        
        cycles_completed = 0
        consecutive_failures = 0
        max_consecutive_failures = 5
        
        try:
            while cycles_completed < max_cycles:
                try:
                    # Check if market is open (unless in test mode)
                    if not self.test_mode and not is_market_hours():
                        logger.info("Market closed, waiting...")
                        time.sleep(60)  # Check every minute
                        continue
                    
                    # Check for too many consecutive failures
                    if consecutive_failures >= max_consecutive_failures:
                        logger.error(f"Too many consecutive failures ({consecutive_failures}). Stopping.")
                        break
                    
                    # Run trading cycle
                    cycle_result = self.run_trading_cycle()
                    
                    if cycle_result is None:
                        consecutive_failures += 1
                        logger.warning(f"Cycle failed. Consecutive failures: {consecutive_failures}")
                    else:
                        consecutive_failures = 0  # Reset on success
                        cycles_completed += 1
                    
                    # Log performance summary every 10 cycles
                    if cycles_completed % 10 == 0:
                        self._log_performance_summary()
                    
                    # Wait for next cycle (unless last cycle)
                    if cycles_completed < max_cycles:
                        logger.info(f"Waiting {cycle_interval}s for next cycle...")
                        time.sleep(cycle_interval)
                        
                except Exception as e:
                    consecutive_failures += 1
                    logger.error(f"Error in trading cycle {cycles_completed + 1}: {e}")
                    
                    # Exponential backoff on errors
                    backoff_time = min(60 * (2 ** consecutive_failures), 3600)  # Max 1 hour
                    logger.info(f"Backing off for {backoff_time}s due to error")
                    time.sleep(backoff_time)
        
        except KeyboardInterrupt:
            logger.info("Trading stopped by user")
        except Exception as e:
            logger.error(f"Critical error in continuous trading: {e}")
        finally:
            logger.info(f"Continuous trading completed after {cycles_completed} cycles")
            logger.info(f"Final consecutive failures: {consecutive_failures}")
            self._log_performance_summary()
    
    def get_performance_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive performance report.
        
        Returns:
            Detailed performance metrics
        """
        # Get account performance
        account_info = self.paper_trader.get_account_info()
        
        # Calculate trading system metrics
        runtime = datetime.now() - self.start_time
        
        # Calculate success rates
        signal_execution_rate = (self.executed_trades / self.total_signals * 100) if self.total_signals > 0 else 0
        
        # Get recent decisions for analysis
        recent_decisions = self.decision_history[-20:] if self.decision_history else []
        
        report = {
            # Trading System Metrics
            'system_metrics': {
                'runtime_hours': runtime.total_seconds() / 3600,
                'trading_cycles': self.trading_cycles,
                'total_signals': self.total_signals,
                'executed_trades': self.executed_trades,
                'skipped_signals': self.skipped_signals,
                'error_count': self.error_count,
                'signal_execution_rate': f"{signal_execution_rate:.1f}%",
                'avg_cycle_time': self._calculate_avg_cycle_time(),
            },
            
            # Account Performance
            'account_performance': account_info,
            
            # Recent Decisions
            'recent_decisions': recent_decisions,
            
            # AI Performance Analysis
            'ai_analysis': self._analyze_ai_performance(),
            
            # Risk Management Stats
            'risk_management': self._analyze_risk_management(),
            
            # Report Metadata
            'report_timestamp': datetime.now().isoformat(),
            'test_mode': self.test_mode
        }
        
        return report
    
    def _calculate_avg_cycle_time(self) -> float:
        """Calculate average cycle execution time"""
        if not self.decision_history:
            return 0.0
        
        # This is a simplified calculation - in production you'd track actual cycle times
        return 30.0  # Placeholder - implement proper tracking
    
    def _analyze_ai_performance(self) -> Dict[str, Any]:
        """Analyze Claude AI decision quality"""
        if not self.decision_history:
            return {'no_data': True}
        
        recent_decisions = self.decision_history[-20:]
        
        # Analyze signal distribution
        signal_counts = {'BUY': 0, 'SELL': 0, 'HOLD': 0}
        confidence_sum = 0
        confidence_count = 0
        
        for decision in recent_decisions:
            signal = decision.get('signal', {})
            signal_type = signal.get('signal', 'HOLD')
            signal_counts[signal_type] = signal_counts.get(signal_type, 0) + 1
            
            confidence = signal.get('confidence', 0)
            if confidence > 0:
                confidence_sum += confidence
                confidence_count += 1
        
        avg_confidence = confidence_sum / confidence_count if confidence_count > 0 else 0
        
        return {
            'recent_signal_distribution': signal_counts,
            'average_confidence': f"{avg_confidence:.2f}",
            'decisions_analyzed': len(recent_decisions),
            'high_confidence_signals': sum(1 for d in recent_decisions 
                                         if d.get('signal', {}).get('confidence', 0) > 0.7)
        }
    
    def _analyze_risk_management(self) -> Dict[str, Any]:
        """Analyze risk management effectiveness"""
        account_info = self.paper_trader.get_account_info()
        positions = self.paper_trader.get_positions()
        
        # Calculate position sizes as percentage of capital
        position_sizes = []
        for symbol, position in positions.items():
            position_value = position['quantity'] * position['current_price']
            position_pct = (position_value / account_info['current_capital']) * 100
            position_sizes.append(position_pct)
        
        return {
            'current_positions': len(positions),
            'capital_utilization': f"{((account_info['current_capital'] - account_info['available_capital']) / account_info['current_capital'] * 100):.1f}%",
            'average_position_size': f"{sum(position_sizes) / len(position_sizes):.1f}%" if position_sizes else "0%",
            'max_position_size': f"{max(position_sizes):.1f}%" if position_sizes else "0%",
            'risk_management_active': True
        }
    
    def _log_performance_summary(self):
        """Log current performance summary"""
        account_info = self.paper_trader.get_account_info()
        
        logger.info("=== PERFORMANCE SUMMARY ===")
        logger.info(f"Capital: ₹{account_info['current_capital']:.2f} ({account_info['total_return']:+.2f}%)")
        logger.info(f"Trades: {account_info['total_trades']} | Win Rate: {account_info['win_rate']:.1f}%")
        logger.info(f"Max Drawdown: {account_info['max_drawdown']:.2f}%")
        logger.info(f"Trading Cycles: {self.trading_cycles}")
        logger.info(f"Signal Execution: {self.executed_trades}/{self.total_signals}")
        logger.info("========================")
    
    def save_performance_report(self, filename: Optional[str] = None) -> str:
        """
        Save detailed performance report to file.
        
        Args:
            filename: Optional custom filename
            
        Returns:
            Path to saved report file
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"claude_trader_report_{timestamp}.json"
        
        report = self.get_performance_report()
        
        # Ensure reports directory exists
        reports_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'reports')
        os.makedirs(reports_dir, exist_ok=True)
        
        filepath = os.path.join(reports_dir, filename)
        
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"Performance report saved to: {filepath}")
        return filepath
    
    def close(self):
        """Cleanup and shutdown"""
        logger.info("Shutting down Claude Trader")
        
        # Generate final report
        final_report = self.get_performance_report()
        
        # Save final report
        self.save_performance_report("final_trading_session.json")
        
        # Close components
        if hasattr(self.data_collector, 'close'):
            self.data_collector.close()
        
        logger.info("Claude Trader shutdown complete")


def main():
    """Test the Claude Trader system"""
    print("🤖 Claude Trader - AI-Powered Trading System")
    print("=" * 50)
    
    # Initialize trader
    trader = ClaudeTrader(initial_capital=10000, test_mode=True)
    
    try:
        # Run a single trading cycle for testing
        print("\n🔄 Running test trading cycle...")
        cycle_result = trader.run_trading_cycle()
        
        print(f"\n📊 Cycle Results:")
        print(f"  Symbols processed: {cycle_result['symbols_processed']}")
        print(f"  Signals generated: {cycle_result['signals_generated']}")
        print(f"  Trades executed: {cycle_result['trades_executed']}")
        print(f"  Cycle duration: {cycle_result['cycle_duration']:.2f}s")
        
        # Display performance
        print("\n📈 Performance Report:")
        report = trader.get_performance_report()
        account = report['account_performance']
        
        print(f"  Capital: ₹{account['current_capital']:.2f}")
        print(f"  Total Return: {account['total_return']:+.2f}%")
        print(f"  Open Positions: {account['open_positions']}")
        print(f"  Total Trades: {account['total_trades']}")
        print(f"  Win Rate: {account['win_rate']:.1f}%")
        
        # Show recent decisions
        if cycle_result['decisions']:
            print(f"\n🧠 Recent Claude Decisions:")
            for decision in cycle_result['decisions'][:3]:  # Show first 3
                signal = decision['signal']
                print(f"  {decision['symbol']}: {signal['signal']} "
                      f"(confidence: {signal.get('confidence', 0):.2f}) "
                      f"- {decision['execution']['status']}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        
    finally:
        trader.close()
        print("\n✅ Test completed!")


if __name__ == "__main__":
    main()
