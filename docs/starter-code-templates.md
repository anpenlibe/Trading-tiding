# Starter Code Templates

## 1. data_collector.py
```python
"""
Module: data_collector.py
Purpose: Fetch and store market data from various sources
Author: [Your name]
Created: 2025-06-11
Modified: 2025-06-11
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import logging
from typing import List, Dict, Optional
import json
import sqlite3

logger = logging.getLogger(__name__)


class DataCollector:
    """
    Handles all market data collection operations.
    
    Attributes:
        symbols (List[str]): List of NSE symbols to track
        db_path (str): Path to SQLite database
    """
    
    def __init__(self, symbols: List[str], db_path: str = "data/market_data.db"):
        self.symbols = [f"{s}.NS" for s in symbols]  # Add NSE suffix
        self.db_path = db_path
        self._init_database()
        
    def _init_database(self):
        """Initialize SQLite database with required tables."""
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS price_data (
                symbol TEXT,
                timestamp DATETIME,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                PRIMARY KEY (symbol, timestamp)
            )
        ''')
        conn.commit()
        conn.close()
        
    def fetch_historical_data(self, period: str = "1mo") -> Dict[str, pd.DataFrame]:
        """
        Fetch historical data for all symbols.
        
        Args:
            period: Time period (1d, 5d, 1mo, 3mo, 6mo, 1y)
            
        Returns:
            Dict mapping symbols to price DataFrames
        """
        data = {}
        for symbol in self.symbols:
            try:
                logger.info(f"Fetching data for {symbol}")
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period=period)
                data[symbol] = hist
                self._save_to_database(symbol, hist)
            except Exception as e:
                logger.error(f"Error fetching {symbol}: {e}")
                
        return data
        
    def _save_to_database(self, symbol: str, data: pd.DataFrame):
        """Save price data to SQLite database."""
        conn = sqlite3.connect(self.db_path)
        data_to_save = data.reset_index()
        data_to_save['symbol'] = symbol
        data_to_save.columns = [col.lower() for col in data_to_save.columns]
        
        # Rename 'date' to 'timestamp' if present
        if 'date' in data_to_save.columns:
            data_to_save.rename(columns={'date': 'timestamp'}, inplace=True)
            
        data_to_save.to_sql('price_data', conn, if_exists='append', index=False)
        conn.close()
        
    def get_latest_prices(self) -> Dict[str, float]:
        """Get latest closing prices for all symbols."""
        prices = {}
        for symbol in self.symbols:
            try:
                ticker = yf.Ticker(symbol)
                data = ticker.history(period="1d")
                if not data.empty:
                    prices[symbol] = data['Close'].iloc[-1]
            except Exception as e:
                logger.error(f"Error getting price for {symbol}: {e}")
                
        return prices


# Example usage
if __name__ == "__main__":
    # Top liquid NSE stocks
    symbols = ["RELIANCE", "TCS", "INFY", "HDFC", "ICICIBANK"]
    
    collector = DataCollector(symbols)
    
    # Fetch historical data
    historical_data = collector.fetch_historical_data(period="1mo")
    
    # Get latest prices
    latest_prices = collector.get_latest_prices()
    print("Latest prices:", latest_prices)
```

## 2. ai_brain.py
```python
"""
Module: ai_brain.py
Purpose: Claude API integration for trading decisions
Author: [Your name]
Created: 2025-06-11
Modified: 2025-06-11
"""

import anthropic
import json
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)


class AIBrain:
    """
    Manages all interactions with Claude API for trading decisions.
    
    Attributes:
        api_key (str): Anthropic API key
        model (str): Claude model to use
    """
    
    def __init__(self, api_key: str, model: str = "claude-3-opus-20240229"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.decision_log = []
        
    def analyze_market(self, market_data: pd.DataFrame, 
                      current_position: Optional[Dict] = None) -> Dict:
        """
        Analyze market data and generate trading decision.
        
        Args:
            market_data: DataFrame with OHLCV data
            current_position: Current position info (if any)
            
        Returns:
            Dict with decision and reasoning
        """
        # Prepare market summary
        market_summary = self._prepare_market_summary(market_data)
        
        # Create prompt
        prompt = self._create_analysis_prompt(market_summary, current_position)
        
        # Get Claude's analysis
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            # Parse response
            decision = self._parse_response(response.content[0].text)
            
            # Log decision
            self._log_decision(market_summary, decision)
            
            return decision
            
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return {"action": "HOLD", "reasoning": "API error", "confidence": 0}
            
    def _prepare_market_summary(self, data: pd.DataFrame) -> Dict:
        """Prepare market data summary for Claude."""
        latest = data.iloc[-1]
        
        return {
            "timestamp": datetime.now().isoformat(),
            "current_price": float(latest['Close']),
            "volume": int(latest['Volume']),
            "day_change": float((latest['Close'] - latest['Open']) / latest['Open'] * 100),
            "5_day_avg": float(data['Close'].tail(5).mean()),
            "20_day_avg": float(data['Close'].tail(20).mean()),
            "volume_avg": float(data['Volume'].tail(20).mean()),
            "volatility": float(data['Close'].pct_change().std() * 100)
        }
        
    def _create_analysis_prompt(self, market_summary: Dict, 
                               position: Optional[Dict]) -> str:
        """Create analysis prompt for Claude."""
        prompt = f"""You are an expert trading analyst. Analyze this market data and provide a trading decision.

Market Data:
- Current Price: ₹{market_summary['current_price']:.2f}
- Day Change: {market_summary['day_change']:.2f}%
- 5-Day Average: ₹{market_summary['5_day_avg']:.2f}
- 20-Day Average: ₹{market_summary['20_day_avg']:.2f}
- Volume vs Average: {market_summary['volume']/market_summary['volume_avg']:.2f}x
- Volatility: {market_summary['volatility']:.2f}%

Current Position: {position if position else 'None'}

Trading Rules:
- Risk only 2% of capital per trade
- Use swing trading (2-5 day holds)
- Consider mean reversion and momentum strategies

Provide your decision in this format:
ACTION: [BUY/SELL/HOLD]
CONFIDENCE: [0.0-1.0]
REASONING: [Your analysis]
STOP_LOSS: [Price if BUY/SELL]
TARGET: [Price if BUY/SELL]
"""
        return prompt
        
    def _parse_response(self, response_text: str) -> Dict:
        """Parse Claude's response into structured format."""
        lines = response_text.strip().split('\n')
        decision = {
            "action": "HOLD",
            "confidence": 0.5,
            "reasoning": "",
            "stop_loss": None,
            "target": None
        }
        
        for line in lines:
            if line.startswith("ACTION:"):
                decision["action"] = line.split(":")[1].strip()
            elif line.startswith("CONFIDENCE:"):
                decision["confidence"] = float(line.split(":")[1].strip())
            elif line.startswith("REASONING:"):
                decision["reasoning"] = line.split(":", 1)[1].strip()
            elif line.startswith("STOP_LOSS:"):
                try:
                    decision["stop_loss"] = float(line.split(":")[1].strip())
                except:
                    pass
            elif line.startswith("TARGET:"):
                try:
                    decision["target"] = float(line.split(":")[1].strip())
                except:
                    pass
                    
        return decision
        
    def _log_decision(self, market_summary: Dict, decision: Dict):
        """Log decision for analysis."""
        log_entry = {
            "timestamp": market_summary["timestamp"],
            "market_data": market_summary,
            "decision": decision
        }
        self.decision_log.append(log_entry)
        
        # Save to file
        with open("data/logs/ai_decisions.json", "a") as f:
            f.write(json.dumps(log_entry) + "\n")


# Example usage
if __name__ == "__main__":
    # You'll need to set your API key
    brain = AIBrain(api_key="your-api-key-here")
    
    # Example with dummy data
    import numpy as np
    dates = pd.date_range(end=datetime.now(), periods=30)
    dummy_data = pd.DataFrame({
        'Open': np.random.randn(30).cumsum() + 100,
        'High': np.random.randn(30).cumsum() + 101,
        'Low': np.random.randn(30).cumsum() + 99,
        'Close': np.random.randn(30).cumsum() + 100,
        'Volume': np.random.randint(1000000, 5000000, 30)
    }, index=dates)
    
    decision = brain.analyze_market(dummy_data)
    print("AI Decision:", decision)
```

## 3. paper_trader.py
```python
"""
Module: paper_trader.py
Purpose: Simulated trading engine for testing strategies
Author: [Your name]
Created: 2025-06-11
Modified: 2025-06-11
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime
import json
import pandas as pd

logger = logging.getLogger(__name__)


class PaperTrader:
    """
    Simulates trading without real money for strategy testing.
    
    Attributes:
        initial_capital (float): Starting capital
        capital (float): Current available capital
        positions (Dict): Current open positions
        trades (List): History of all trades
    """
    
    def __init__(self, initial_capital: float = 1000.0):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.positions = {}
        self.trades = []
        self.trade_id = 0
        
    def execute_trade(self, symbol: str, action: str, price: float, 
                     quantity: int, stop_loss: Optional[float] = None,
                     target: Optional[float] = None) -> Dict:
        """
        Execute a paper trade.
        
        Args:
            symbol: Stock symbol
            action: BUY or SELL
            price: Execution price
            quantity: Number of shares
            stop_loss: Stop loss price
            target: Target price
            
        Returns:
            Trade confirmation dict
        """
        trade_value = price * quantity
        commission = 20  # Flat ₹20 brokerage
        
        if action == "BUY":
            total_cost = trade_value + commission
            
            if total_cost > self.capital:
                logger.warning(f"Insufficient capital. Need ₹{total_cost}, have ₹{self.capital}")
                return {"status": "REJECTED", "reason": "Insufficient capital"}
                
            self.capital -= total_cost
            
            # Add to positions
            if symbol in self.positions:
                # Average the position
                old_pos = self.positions[symbol]
                total_qty = old_pos['quantity'] + quantity
                avg_price = (old_pos['avg_price'] * old_pos['quantity'] + 
                           price * quantity) / total_qty
                self.positions[symbol] = {
                    'quantity': total_qty,
                    'avg_price': avg_price,
                    'stop_loss': stop_loss,
                    'target': target
                }
            else:
                self.positions[symbol] = {
                    'quantity': quantity,
                    'avg_price': price,
                    'stop_loss': stop_loss,
                    'target': target
                }
                
        elif action == "SELL":
            if symbol not in self.positions:
                logger.warning(f"No position in {symbol} to sell")
                return {"status": "REJECTED", "reason": "No position"}
                
            position = self.positions[symbol]
            
            if quantity > position['quantity']:
                logger.warning(f"Cannot sell {quantity}, only have {position['quantity']}")
                return {"status": "REJECTED", "reason": "Insufficient quantity"}
                
            # Calculate P&L
            buy_value = position['avg_price'] * quantity
            sell_value = price * quantity - commission
            pnl = sell_value - buy_value
            
            self.capital += sell_value
            
            # Update or remove position
            if quantity == position['quantity']:
                del self.positions[symbol]
            else:
                position['quantity'] -= quantity
                
        # Record trade
        trade = {
            'trade_id': self.trade_id,
            'timestamp': datetime.now().isoformat(),
            'symbol': symbol,
            'action': action,
            'price': price,
            'quantity': quantity,
            'commission': commission,
            'stop_loss': stop_loss,
            'target': target,
            'capital_after': self.capital
        }
        
        if action == "SELL" and 'pnl' in locals():
            trade['pnl'] = pnl
            
        self.trades.append(trade)
        self.trade_id += 1
        
        # Log trade
        logger.info(f"Executed: {action} {quantity} {symbol} @ ₹{price}")
        self._save_trade(trade)
        
        return {"status": "EXECUTED", "trade": trade}
        
    def check_stop_loss_target(self, current_prices: Dict[str, float]) -> List[Dict]:
        """Check if any positions hit stop loss or target."""
        triggered_trades = []
        
        for symbol, position in list(self.positions.items()):
            if symbol in current_prices:
                current_price = current_prices[symbol]
                
                # Check stop loss
                if position['stop_loss'] and current_price <= position['stop_loss']:
                    trade = self.execute_trade(
                        symbol, "SELL", current_price, 
                        position['quantity']
                    )
                    trade['trigger'] = "STOP_LOSS"
                    triggered_trades.append(trade)
                    
                # Check target
                elif position['target'] and current_price >= position['target']:
                    trade = self.execute_trade(
                        symbol, "SELL", current_price,
                        position['quantity']
                    )
                    trade['trigger'] = "TARGET"
                    triggered_trades.append(trade)
                    
        return triggered_trades
        
    def get_portfolio_value(self, current_prices: Dict[str, float]) -> float:
        """Calculate total portfolio value."""
        positions_value = 0
        
        for symbol, position in self.positions.items():
            if symbol in current_prices:
                positions_value += current_prices[symbol] * position['quantity']
                
        return self.capital + positions_value
        
    def get_performance_metrics(self, current_prices: Dict[str, float]) -> Dict:
        """Calculate performance metrics."""
        portfolio_value = self.get_portfolio_value(current_prices)
        total_return = (portfolio_value - self.initial_capital) / self.initial_capital * 100
        
        # Calculate win rate
        completed_trades = [t for t in self.trades if t.get('pnl') is not None]
        winning_trades = [t for t in completed_trades if t['pnl'] > 0]
        
        win_rate = len(winning_trades) / len(completed_trades) * 100 if completed_trades else 0
        
        return {
            'portfolio_value': portfolio_value,
            'total_return': total_return,
            'capital': self.capital,
            'positions_value': portfolio_value - self.capital,
            'number_of_trades': len(self.trades),
            'open_positions': len(self.positions),
            'win_rate': win_rate
        }
        
    def _save_trade(self, trade: Dict):
        """Save trade to file."""
        with open("data/logs/paper_trades.json", "a") as f:
            f.write(json.dumps(trade) + "\n")


# Example usage
if __name__ == "__main__":
    trader = PaperTrader(initial_capital=1000)
    
    # Example trade
    result = trader.execute_trade(
        symbol="RELIANCE.NS",
        action="BUY",
        price=2850,
        quantity=1,
        stop_loss=2800,
        target=2950
    )
    print("Trade result:", result)
    
    # Check performance
    current_prices = {"RELIANCE.NS": 2900}
    metrics = trader.get_performance_metrics(current_prices)
    print("Performance:", metrics)
```

## 4. config.py
```python
"""
Module: config.py
Purpose: Configuration settings for the trading bot
Author: [Your name]
Created: 2025-06-11
Modified: 2025-06-11
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ZERODHA_API_KEY = os.getenv("ZERODHA_API_KEY")  # For future use
ZERODHA_API_SECRET = os.getenv("ZERODHA_API_SECRET")  # For future use

# Trading Parameters
INITIAL_CAPITAL = 1000.0
MAX_RISK_PER_TRADE = 0.02  # 2%
MAX_DAILY_LOSS = 0.06  # 6%
MAX_DRAWDOWN = 0.20  # 20%

# Symbols to Trade
SYMBOLS = [
    "RELIANCE",
    "TCS", 
    "INFY",
    "HDFC",
    "ICICIBANK",
    "SBIN",
    "BHARTIARTL",
    "ITC",
    "KOTAKBANK",
    "LT"
]

# Market Hours (IST)
MARKET_OPEN = "09:15"
MARKET_CLOSE = "15:30"

# Logging
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Data Settings
DATA_PATH = "data"
DB_PATH = os.path.join(DATA_PATH, "market_data.db")

# Claude API Settings
CLAUDE_MODEL = "claude-3-opus-20240229"
CLAUDE_MAX_TOKENS = 1000

# Strategy Settings
STRATEGIES = {
    "mean_reversion": {
        "enabled": True,
        "lookback_period": 20,
        "entry_threshold": 0.02,  # 2% below mean
        "exit_threshold": 0.01   # 1% above mean
    },
    "momentum": {
        "enabled": False,  # Start with one strategy
        "lookback_period": 10,
        "breakout_threshold": 0.03
    }
}
```

## 5. main.py - Main Entry Point
```python
"""
Module: main.py
Purpose: Main entry point for the trading bot
Author: [Your name]
Created: 2025-06-11
Modified: 2025-06-11
"""

import logging
import time
from datetime import datetime
import schedule
import config
from src.data_collector import DataCollector
from src.ai_brain import AIBrain
from src.paper_trader import PaperTrader

# Set up logging
logging.basicConfig(
    level=config.LOG_LEVEL,
    format=config.LOG_FORMAT,
    handlers=[
        logging.FileHandler("data/logs/trading_bot.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class TradingBot:
    """Main trading bot orchestrator."""
    
    def __init__(self):
        logger.info("Initializing Trading Bot...")
        
        # Initialize components
        self.data_collector = DataCollector(config.SYMBOLS)
        self.ai_brain = AIBrain(config.ANTHROPIC_API_KEY)
        self.paper_trader = PaperTrader(config.INITIAL_CAPITAL)
        
        # State
        self.is_market_hours = False
        
    def run(self):
        """Main run loop."""
        logger.info("Trading Bot started!")
        
        # Schedule tasks
        schedule.every().day.at("09:00").do(self.morning_routine)
        schedule.every().day.at("09:14").do(self.pre_market_analysis)
        schedule.every(5).minutes.do(self.check_positions)
        schedule.every().day.at("15:45").do(self.end_of_day_routine)
        
        # Run initial setup
        self.morning_routine()
        
        # Main loop
        while True:
            schedule.run_pending()
            
            # During market hours, run more frequently
            if self.is_market_hours:
                self.trading_loop()
                
            time.sleep(60)  # Check every minute
            
    def morning_routine(self):
        """Morning setup and checks."""
        logger.info("Running morning routine...")
        
        # Fetch historical data
        self.data_collector.fetch_historical_data(period="1mo")
        
        # Check system health
        self.system_health_check()
        
        # Load previous day's performance
        self.review_performance()
        
    def pre_market_analysis(self):
        """Pre-market analysis and preparation."""
        logger.info("Running pre-market analysis...")
        
        # Get latest data
        historical_data = self.data_collector.fetch_historical_data(period="5d")
        
        # Analyze each symbol
        for symbol in config.SYMBOLS:
            symbol_ns = f"{symbol}.NS"
            if symbol_ns in historical_data:
                analysis = self.ai_brain.analyze_market(
                    historical_data[symbol_ns],
                    self.paper_trader.positions.get(symbol_ns)
                )
                logger.info(f"{symbol}: {analysis['action']} "
                          f"(confidence: {analysis['confidence']})")
                
    def trading_loop(self):
        """Main trading logic - runs during market hours."""
        current_time = datetime.now().strftime("%H:%M")
        
        # Check if market is open
        if current_time >= config.MARKET_OPEN and current_time <= config.MARKET_CLOSE:
            self.is_market_hours = True
            
            # Get latest prices
            latest_prices = self.data_collector.get_latest_prices()
            
            # Check stop losses and targets
            triggered = self.paper_trader.check_stop_loss_target(latest_prices)
            if triggered:
                logger.info(f"Triggered trades: {triggered}")
                
            # Analyze for new opportunities
            for symbol in config.SYMBOLS:
                symbol_ns = f"{symbol}.NS"
                
                # Skip if already have position
                if symbol_ns in self.paper_trader.positions:
                    continue
                    
                # Get recent data
                ticker_data = self.data_collector.fetch_historical_data(period="5d")
                
                if symbol_ns in ticker_data:
                    # Get AI analysis
                    decision = self.ai_brain.analyze_market(ticker_data[symbol_ns])
                    
                    # Execute if confident
                    if decision['confidence'] > 0.7:
                        if decision['action'] == "BUY":
                            # Calculate position size (2% risk)
                            capital = self.paper_trader.capital
                            risk_amount = capital * config.MAX_RISK_PER_TRADE
                            
                            # Simple position sizing
                            quantity = 1  # Start with 1 share for testing
                            
                            result = self.paper_trader.execute_trade(
                                symbol=symbol_ns,
                                action="BUY",
                                price=latest_prices.get(symbol_ns, 0),
                                quantity=quantity,
                                stop_loss=decision.get('stop_loss'),
                                target=decision.get('target')
                            )
                            
                            logger.info(f"Trade result: {result}")
        else:
            self.is_market_hours = False
            
    def check_positions(self):
        """Regular position monitoring."""
        if not self.is_market_hours:
            return
            
        latest_prices = self.data_collector.get_latest_prices()
        metrics = self.paper_trader.get_performance_metrics(latest_prices)
        
        logger.info(f"Portfolio value: ₹{metrics['portfolio_value']:.2f} "
                   f"({metrics['total_return']:+.2f}%)")
                   
    def end_of_day_routine(self):
        """End of day processing."""
        logger.info("Running end of day routine...")
        
        # Get final prices
        latest_prices = self.data_collector.get_latest_prices()
        
        # Generate performance report
        metrics = self.paper_trader.get_performance_metrics(latest_prices)
        
        # Save daily report
        report = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "metrics": metrics,
            "trades": len([t for t in self.paper_trader.trades 
                          if t['timestamp'].startswith(datetime.now().strftime("%Y-%m-%d"))]),
            "positions": self.paper_trader.positions
        }
        
        with open(f"docs/performance/{report['date']}.json", "w") as f:
            json.dump(report, f, indent=2)
            
        logger.info(f"Day complete. Return: {metrics['total_return']:+.2f}%")
        
    def system_health_check(self):
        """Check system health."""
        checks = {
            "Data API": self._check_data_api(),
            "Claude API": self._check_claude_api(),
            "Disk Space": self._check_disk_space(),
        }
        
        for component, status in checks.items():
            if not status:
                logger.error(f"{component} check failed!")
            else:
                logger.info(f"{component}: OK")
                
    def _check_data_api(self):
        """Check if data API is working."""
        try:
            prices = self.data_collector.get_latest_prices()
            return len(prices) > 0
        except:
            return False
            
    def _check_claude_api(self):
        """Check if Claude API is working."""
        try:
            response = self.ai_brain.client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=10,
                messages=[{"role": "user", "content": "test"}]
            )
            return True
        except:
            return False
            
    def _check_disk_space(self):
        """Check available disk space."""
        import shutil
        stat = shutil.disk_usage(".")
        # Need at least 100MB free
        return stat.free > 100 * 1024 * 1024
        
    def review_performance(self):
        """Review previous day's performance."""
        # Implementation for reviewing past performance
        pass


if __name__ == "__main__":
    bot = TradingBot()
    bot.run()
```

## 6. requirements.txt
```
# Core dependencies
pandas==2.0.3
numpy==1.24.3
yfinance==0.2.18
anthropic==0.3.0
python-dotenv==1.0.0

# Technical analysis
ta-lib==0.4.28
pandas-ta==0.3.14b

# Scheduling and utilities
schedule==1.2.0
pytz==2023.3

# Testing
pytest==7.4.0
pytest-cov==4.1.0
pytest-mock==3.11.1

# Logging and monitoring
colorlog==6.7.0

# Future additions (commented out for now)
# vectorbt==0.26.0  # For backtesting
# ccxt==4.0.0  # For crypto trading
# streamlit==1.25.0  # For web dashboard
```

## 7. .env.template
```
# API Keys
ANTHROPIC_API_KEY=your-claude-api-key-here
ZERODHA_API_KEY=future-use
ZERODHA_API_SECRET=future-use

# Environment
ENVIRONMENT=development
```

## 8. Quick Start Script (setup.sh)
```bash
#!/bin/bash

echo "Setting up Trading Bot project..."

# Create directory structure
mkdir -p src/{utils,strategies}
mkdir -p data/{historical,live,logs}
mkdir -p docs/{performance,decisions,architecture}
mkdir -p tests/{unit,integration}
mkdir -p prompts
mkdir -p scripts
mkdir -p notebooks

# Create empty __init__.py files
touch src/__init__.py
touch src/utils/__init__.py
touch tests/__init__.py
touch tests/unit/__init__.py
touch tests/integration/__init__.py

# Copy .env template
cp .env.template .env
echo "⚠️  Remember to update .env with your API keys!"

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Initialize git
git init
git add .
git commit -m "Initial commit: Project setup"

echo "✅ Setup complete! Next steps:"
echo "1. Update .env with your Anthropic API key"
echo "2. Run: source venv/bin/activate"
echo "3. Test data collection: python src/data_collector.py"
echo "4. Start development!"
```