# System Architecture Design

## Overview

The trading bot follows a modular, event-driven architecture designed for scalability and maintainability.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    External Data Sources                      │
│  ┌─────────┐  ┌──────────┐  ┌────────────┐  ┌──────────┐  │
│  │Dhan API │  │ yfinance │  │Twelve Data │  │ Zerodha  │  │
│  └────┬────┘  └─────┬────┘  └─────┬──────┘  └────┬─────┘  │
└───────┼─────────────┼──────────────┼──────────────┼────────┘
        └─────────────┴──────────────┴──────────────┘
                              │
                    ┌─────────▼─────────┐
                    │  Data Collector   │
                    │  (Fallback Chain) │
                    └─────────┬─────────┘
                              │
                ┌─────────────┼─────────────┐
                │             │             │
        ┌───────▼──────┐ ┌───▼────┐ ┌─────▼──────┐
        │   Database   │ │ Cache  │ │ Validators │
        │   (SQLite)   │ │(Memory)│ │            │
        └───────┬──────┘ └───┬────┘ └─────┬──────┘
                └─────────────┼─────────────┘
                              │
                    ┌─────────▼─────────┐
                    │ Indicator Engine  │
                    │ (SMA,RSI,MACD)    │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │    AI Brain       │
                    │  (Claude API)     │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │  Paper Trader     │
                    │  (Simulation)     │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │Risk Management    │
                    │(Position Sizing)  │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │  Order Executor   │
                    │ (Future: Zerodha) │
                    └───────────────────┘
```

## Core Components

### 1. Data Layer
- **Data Collector**: Orchestrates data fetching with fallback mechanism
- **Database**: SQLite for development, TimescaleDB for production
- **Cache**: In-memory cache with 5-minute TTL
- **Validators**: Ensure data quality and consistency

### 2. Processing Layer
- **Indicator Engine**: Calculates technical indicators
- **AI Brain**: Claude API integration for decision making
- **Risk Manager**: Position sizing and risk calculations

### 3. Execution Layer
- **Paper Trader**: Simulated trading for testing
- **Order Executor**: Future integration with Zerodha

## Design Patterns

### 1. **Strategy Pattern** (for APIs)
- Abstract base class for market data sources
- Concrete implementations for each API
- Easy to add new data sources

### 2. **Chain of Responsibility** (for fallbacks)
- Primary → Secondary → Tertiary → Cache
- Each handler tries to process or passes to next

### 3. **Observer Pattern** (for events)
- Market data updates trigger indicator calculations
- Indicator updates trigger AI analysis
- AI decisions trigger trade execution

### 4. **Singleton Pattern** (for managers)
- Single instance of DataCollector
- Single instance of RiskManager
- Ensures consistent state

## Data Flow

1. **Collection Phase** (Every 5 minutes)
   - Fetch data from primary source
   - Fallback if primary fails
   - Validate data
   - Store in database
   - Update cache

2. **Analysis Phase**
   - Calculate indicators
   - Send to AI Brain
   - Generate trading signals

3. **Execution Phase**
   - Risk assessment
   - Position sizing
   - Order placement (simulated/real)

## Scalability Considerations

### Horizontal Scaling
- Stateless components can be replicated
- Database can be sharded by symbol
- Cache can be distributed (Redis)

### Vertical Scaling
- Async operations for I/O bound tasks
- Multiprocessing for CPU bound calculations
- Efficient data structures (numpy, pandas)

## Security Measures

1. **API Keys**: Environment variables, never in code
2. **Database**: Encrypted connections (future)
3. **Logging**: No sensitive data in logs
4. **Access Control**: Role-based permissions (future)

## Migration Paths

### SQLite → TimescaleDB
- Compatible SQL syntax
- Gradual migration possible
- Performance benefits for time-series

### Memory Cache → Redis
- Similar interface
- Persistent cache option
- Distributed caching

### Single Machine → Distributed
- Microservices architecture
- Message queue integration
- Load balancing

## Error Handling Strategy

1. **Graceful Degradation**: System continues with reduced functionality
2. **Circuit Breakers**: Prevent cascade failures
3. **Retry Logic**: Exponential backoff for transient failures
4. **Comprehensive Logging**: All errors logged with context

## Performance Targets

- Data collection: < 1 second per symbol
- Indicator calculation: < 100ms per symbol
- AI decision: < 5 seconds per analysis
- Total cycle time: < 1 minute for all symbols

## Future Enhancements

1. **WebSocket Integration**: Real-time data feeds
2. **Multi-Strategy Support**: Multiple AI models
3. **Portfolio Optimization**: Modern portfolio theory
4. **Advanced Risk Management**: VaR, stress testing
5. **Cloud Deployment**: Azure integration