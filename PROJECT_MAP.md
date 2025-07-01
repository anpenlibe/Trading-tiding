# Project Structure Map

## Current Working Structure
```
src/                    # ✅ KEEP - All working modules
├── ai_brain.py        # AI decision making  
├── paper_trader.py    # Trade execution (NEEDS FIX)
├── risk_manager.py    # Risk management
├── data_collector.py  # Market data
├── config.py          # Configuration
└── utils/             # Utilities

tests/                  # ✅ KEEP - Test files
data/                   # ✅ KEEP - Data storage
├── logs/              # Log files
├── historical/        # Historical data
└── market_data.sqlite # Database

scripts/                # ✅ KEEP - Utility scripts
notebooks/              # ✅ KEEP - Jupyter notebooks
```

## New Components (To Build)
```
new_components/
├── triggers/          # Smart trigger system
├── context/           # ChromaDB integration  
└── monitoring/        # Enhanced monitoring
```

## Entry Points
- `claude_trader.py` - Main trading system
- `historical_simulator.py` - Backtesting
- `system_check.py` - System validation
