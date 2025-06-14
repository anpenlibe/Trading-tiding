# Day 1 Decisions Log - 2025-06-10

## Setup Decisions

### 1. **Project Name and Location**
- **Decision**: Named project `trading-tiding` instead of `trading-bot`
- **Rationale**: Personal preference
- **Location**: `~/trading-tiding/`

### 2. **Python Version**
- **Issue**: Python 3.13 compatibility problems with numpy/pandas
- **Decision**: Use pyenv to install Python 3.11.9
- **Rationale**: Better package compatibility
- **Implementation**: 
  ```bash
  pyenv install 3.11.9
  pyenv local 3.11.9
  ```

### 3. **Development Environment**
- **Decision**: Use Linux with nvim as primary editor
- **Git**: Initialized and pushed to personal repository

### 4. **Initial Architecture**
- **Decision**: Start simple, avoid over-engineering
- **Learning**: Previous attempt was too complex with "AI company" roleplay

## Technical Stack Decisions

### Core Technologies
- **Language**: Python 3.11.9
- **Database**: SQLite (with migration path to TimescaleDB)
- **APIs**: Yahoo Finance for initial testing
- **AI**: Claude API for trading decisions

### Development Principles
1. Start simple, add complexity later
2. Working code > perfect architecture
3. Test with paper trading extensively (200+ trades before live)
4. Documentation important but don't overdo it

## Risk Parameters
- **Initial Capital**: ₹1,000
- **Risk per trade**: 2% (₹20)
- **Max drawdown**: 20%
- **Goal**: Cover ₹4,000/month AI subscription costs

## Next Steps Decided
1. Set up basic data collection
2. Build paper trading system
3. Integrate Claude API
4. Run 50+ paper trades in Week 1