# 📚 Project Table of Contents - Central Navigation

**Navigation Hub for the Claude AI Trading System**  
**Version**: 3.0 (Post Phase 3 Reorganization)  
**Last Updated**: January 2025  

---

## 🎯 Quick Start Navigation

| **I Want To...** | **Go To** | **Description** |
|-------------------|-----------|-----------------|
| **🚀 Run the trading system** | [README.md](./README.md) | Main project overview and quick start |
| **🎯 Check complete system status** | [SYSTEM_STATUS.md](./SYSTEM_STATUS.md) | **⭐ CENTRAL TRACKING HUB** - Single source of truth |
| **📊 Check system architecture** | [SYSTEM_ARCHITECTURE.md](./SYSTEM_ARCHITECTURE.md) | Architecture lookup table for changes |
| **🗺️ See current system structure** | [PROJECT_MAP.md](./PROJECT_MAP.md) | Current system structure and components |
| **🏗️ Understand the code structure** | [src/README.md](./src/README.md) | Detailed module documentation |
| **🧪 Run tests** | [tests/README.md](./tests/README.md) | Testing guide and test structure |
| **📱 Use applications** | [apps/README.md](./apps/README.md) | Application usage guide |
| **📋 See project history** | [docs/](./docs/) | Phase documentation and development history |
| **🔧 For developers** | [CLAUDE_CODE_RULES.md](./CLAUDE_CODE_RULES.md) | Development guidelines and rules |

---

## 📂 Directory Structure Guide

```
trading-tiding/
│
├── 📋 PROJECT_TOC.md              ← YOU ARE HERE - Central navigation
├── 📖 README.md                   ← Main project overview (USER FOCUSED)
├── 🏗️ SYSTEM_ARCHITECTURE.md     ← **CHANGE IMPACT LOOKUP TABLE** 
├── 🔧 CLAUDE_CODE_RULES.md       ← Development rules and guidelines
│
├── 📱 apps/                       ← Executable applications
│   ├── README.md                  ← Application usage guide
│   ├── trader.py                  ← Main trading system
│   ├── backtest.py               ← Historical backtesting
│   ├── data_collector.py         ← Data collection utility
│   ├── monitor.py                ← System monitoring
│   └── health_check.py           ← System health verification
│
├── 💻 src/                        ← Core source code
│   ├── README.md                  ← Module documentation hub
│   │
│   ├── 🧠 core/                   ← Business logic layer
│   │   ├── README.md              ← Core modules guide
│   │   ├── ai_brain.py           ← Claude AI integration
│   │   ├── risk_manager.py       ← Risk management
│   │   ├── paper_trader.py       ← Trade execution
│   │   └── indicator_engine.py   ← Technical analysis
│   │
│   ├── 📊 data/                   ← Data layer
│   │   ├── README.md              ← Data handling guide
│   │   ├── config.py             ← Configuration management
│   │   ├── data_sources.py       ← API implementations
│   │   ├── stock_registry.py     ← Stock universe
│   │   ├── database.py           ← Database operations
│   │   ├── cache.py              ← Caching utilities
│   │   └── validator.py          ← Data validation
│   │
│   ├── 🤖 ai/                     ← AI components
│   │   ├── README.md              ← AI modules guide
│   │   └── prompt_builder.py     ← Prompt engineering
│   │
│   ├── ⚡ alerts/                 ← Alert system
│   │   ├── README.md              ← Alert system guide
│   │   ├── alert_engine.py       ← Alert orchestration
│   │   ├── rules.py              ← Alert conditions
│   │   └── monitor.py            ← Alert monitoring
│   │
│   ├── 📈 monitoring/             ← System monitoring
│   │   ├── README.md              ← Monitoring guide
│   │   ├── performance.py        ← Performance tracking
│   │   ├── dashboard.py          ← System dashboard
│   │   └── error_tracker.py      ← Error monitoring
│   │
│   ├── 🔧 utils/                  ← Utilities
│   │   ├── README.md              ← Utilities guide
│   │   ├── logger.py             ← Logging infrastructure
│   │   ├── db_optimizer.py       ← Database optimization
│   │   └── retry.py              ← Retry mechanisms
│   │
│   ├── data_collector.py          ← Data orchestration (main data module)
│   ├── interfaces.py              ← System contracts/interfaces
│   └── exceptions.py              ← Custom exceptions
│
├── 🧪 tests/                      ← Test suite
│   ├── README.md                  ← Testing guide
│   ├── conftest.py               ← Test fixtures
│   ├── unit/                     ← Unit tests
│   ├── integration/              ← Integration tests
│   └── test_alerts.py            ← Alert system tests
│
├── 📚 docs/                       ← Documentation
│   ├── README.md                  ← Documentation index
│   ├── api/                      ← Auto-generated API docs
│   ├── guides/                   ← User guides
│   ├── PHASE_*.md                ← Development history
│   └── *.md                      ← Various documentation files
│
├── 🛠️ scripts/                   ← Utility scripts
│   ├── README.md                  ← Scripts usage guide
│   └── generate_zerodha_token.py ← Zerodha OAuth token generator
│
├── ⚙️ Configuration Files
│   ├── .env.template             ← Environment variables template
│   ├── requirements.txt          ← Python dependencies
│   └── instruments.csv           ← Zerodha instrument data
│
└── 🔧 System Files
    ├── generate_docs.py           ← Documentation generator
    ├── optimize_system.py         ← System optimizer
    └── run_tests.py              ← Test runner
```

---

## 🎯 Use Case Navigation

### **👤 For End Users (Trading)**
1. **Getting Started**: [README.md](./README.md) → Quick Start section
2. **Live Data Setup**: [scripts/README.md](./scripts/README.md) → Zerodha token generation
3. **Running Trading**: [apps/README.md](./apps/README.md) → trader.py guide
4. **Backtesting**: [apps/README.md](./apps/README.md) → backtest.py guide
5. **Monitoring**: [apps/README.md](./apps/README.md) → monitor.py guide
6. **Configuration**: [src/data/README.md](./src/data/README.md) → config.py section

### **🔧 For Developers (Code)**
1. **Architecture Overview**: [SYSTEM_ARCHITECTURE.md](./SYSTEM_ARCHITECTURE.md)
2. **Module Details**: [src/README.md](./src/README.md)
3. **Development Rules**: [CLAUDE_CODE_RULES.md](./CLAUDE_CODE_RULES.md)
4. **Testing Guide**: [tests/README.md](./tests/README.md)
5. **API Reference**: [docs/api/](./docs/api/)

### **🧠 For AI/ML Engineers**
1. **AI Brain Module**: [src/core/README.md](./src/core/README.md) → ai_brain.py
2. **Prompt Engineering**: [src/ai/README.md](./src/ai/README.md) → prompt_builder.py
3. **Alert System**: [src/alerts/README.md](./src/alerts/README.md)
4. **Performance Monitoring**: [src/monitoring/README.md](./src/monitoring/README.md)

### **📊 For Data Engineers**
1. **Data Pipeline**: [src/data/README.md](./src/data/README.md)
2. **Database Operations**: [src/data/README.md](./src/data/README.md) → database.py
3. **Data Collection**: [src/README.md](./src/README.md) → data_collector.py
4. **API Integrations**: [src/data/README.md](./src/data/README.md) → data_sources.py

### **🧪 For QA/Testing**
1. **Test Structure**: [tests/README.md](./tests/README.md)
2. **Running Tests**: [README.md](./README.md) → Testing section
3. **Test Coverage**: [tests/README.md](./tests/README.md) → Coverage section
4. **Integration Testing**: [tests/README.md](./tests/README.md) → Integration section

---

## 📋 Documentation Hierarchy

### **Level 1: Project Overview**
- **README.md** - Main project documentation (USER FOCUSED)
- **SYSTEM_ARCHITECTURE.md** - Technical architecture (DEVELOPER FOCUSED)
- **PROJECT_TOC.md** - This navigation file

### **Level 2: Area Documentation**
- **apps/README.md** - Application usage
- **src/README.md** - Source code overview
- **tests/README.md** - Testing guide
- **docs/README.md** - Documentation index

### **Level 3: Module Documentation**
- **src/core/README.md** - Core modules
- **src/data/README.md** - Data handling
- **src/ai/README.md** - AI components
- **src/alerts/README.md** - Alert system
- **src/monitoring/README.md** - Monitoring
- **src/utils/README.md** - Utilities

### **Level 4: Specialized Documentation**
- **docs/api/\*.md** - Auto-generated API docs
- **docs/guides/\*.md** - User guides
- **docs/PHASE_\*.md** - Development history

---

## 🔍 Finding What You Need

### **🎯 Quick Search Patterns**
```bash
# Find all documentation about a topic
find . -name "*.md" -exec grep -l "topic" {} \;

# Find README for a specific area
find . -name "README.md" | grep area_name

# Find all configuration documentation
grep -r "config\|Config\|CONFIG" --include="*.md" .

# Find all API documentation
find docs/api/ -name "*.md"
```

### **🔗 Common Cross-References**
| **Topic** | **Primary Doc** | **Related Docs** |
|-----------|----------------|------------------|
| **Architecture** | SYSTEM_ARCHITECTURE.md | src/README.md, apps/README.md |
| **Configuration** | src/data/README.md | .env.template, docs/guides/ |
| **AI Integration** | src/core/README.md | src/ai/README.md, docs/api/ai_brain.md |
| **Testing** | tests/README.md | run_tests.py, docs/guides/ |
| **Data Pipeline** | src/data/README.md | src/README.md, apps/README.md |
| **Monitoring** | src/monitoring/README.md | apps/README.md, optimize_system.py |

---

## 🚀 Development Workflow

### **🆕 For New Features**
1. **Check Architecture Impact**: [SYSTEM_ARCHITECTURE.md](./SYSTEM_ARCHITECTURE.md) → Change Impact Matrix
2. **Find Related Modules**: Use dependency chains in architecture doc
3. **Read Module Documentation**: Relevant README.md files
4. **Follow Development Rules**: [CLAUDE_CODE_RULES.md](./CLAUDE_CODE_RULES.md)
5. **Update Tests**: [tests/README.md](./tests/README.md)
6. **Update Documentation**: Update relevant README files

### **🐛 For Bug Fixes**
1. **Identify Module**: [src/README.md](./src/README.md) → Module Status Matrix
2. **Check Dependencies**: [SYSTEM_ARCHITECTURE.md](./SYSTEM_ARCHITECTURE.md) → Dependency Chains
3. **Find Tests**: [tests/README.md](./tests/README.md) → Test Coverage section
4. **Check Configuration**: [src/data/README.md](./src/data/README.md) → config.py section

### **📊 For Performance Issues**
1. **Check Monitoring**: [src/monitoring/README.md](./src/monitoring/README.md)
2. **Review Architecture**: [SYSTEM_ARCHITECTURE.md](./SYSTEM_ARCHITECTURE.md) → Data Flow Architecture
3. **Optimize Database**: optimize_system.py documentation
4. **Review Caching**: [src/data/README.md](./src/data/README.md) → cache.py section

---

## 📈 Future Improvements Tracking

### **🧠 AI Context Memory**
- **Architecture Impact**: [SYSTEM_ARCHITECTURE.md](./SYSTEM_ARCHITECTURE.md) → Future Improvements section
- **Implementation Guide**: [src/ai/README.md](./src/ai/README.md) → Future enhancements
- **Testing Impact**: [tests/README.md](./tests/README.md) → Test renewal section

### **🔄 Test Suite Renewal**
- **Current Status**: [tests/README.md](./tests/README.md) → Test status
- **Renewal Plan**: [CLAUDE_CODE_RULES.md](./CLAUDE_CODE_RULES.md) → Testing standards
- **Priority Areas**: [SYSTEM_ARCHITECTURE.md](./SYSTEM_ARCHITECTURE.md) → Critical System Points

### **📊 Multi-Timestamp Data**
- **Data Pipeline Changes**: [src/data/README.md](./src/data/README.md) → data_collector.py
- **AI Integration**: [src/core/README.md](./src/core/README.md) → ai_brain.py
- **Configuration Impact**: [src/data/README.md](./src/data/README.md) → config.py

### **🔌 Fallback API Integration**
- **Data Sources**: [src/data/README.md](./src/data/README.md) → data_sources.py
- **Configuration**: [src/data/README.md](./src/data/README.md) → config.py
- **Testing**: [tests/README.md](./tests/README.md) → Data source tests

### **📦 Stock Abstraction**
- **Stock Registry**: [src/data/README.md](./src/data/README.md) → stock_registry.py
- **Configuration Cleanup**: [SYSTEM_ARCHITECTURE.md](./SYSTEM_ARCHITECTURE.md) → Configuration Impact Map
- **System-wide Impact**: All modules using hardcoded symbols

---

## 🎯 Maintenance Checklist

### **📅 Regular Maintenance (Weekly)**
- [ ] Review [SYSTEM_ARCHITECTURE.md](./SYSTEM_ARCHITECTURE.md) for accuracy
- [ ] Update module status in [src/README.md](./src/README.md)
- [ ] Check test coverage in [tests/README.md](./tests/README.md)
- [ ] Update performance metrics in [src/monitoring/README.md](./src/monitoring/README.md)

### **🔄 After Major Changes**
- [ ] Update [SYSTEM_ARCHITECTURE.md](./SYSTEM_ARCHITECTURE.md) FIRST
- [ ] Update affected module README files
- [ ] Update test documentation
- [ ] Regenerate API documentation
- [ ] Update this PROJECT_TOC.md if structure changed

### **📦 Before Releases**
- [ ] All README files current
- [ ] All examples working
- [ ] All links functional
- [ ] API documentation complete
- [ ] Development history updated

---

## 🔗 External Links & Resources

### **Development Tools**
- **Claude Code Integration**: [CLAUDE_CODE_RULES.md](./CLAUDE_CODE_RULES.md)
- **Testing Framework**: [tests/README.md](./tests/README.md) → Testing tools
- **Documentation Generation**: generate_docs.py
- **System Optimization**: optimize_system.py

### **API References**
- **Anthropic Claude API**: [src/core/README.md](./src/core/README.md) → ai_brain.py
- **Zerodha Kite Connect**: [src/data/README.md](./src/data/README.md) → data_sources.py
- **System APIs**: [docs/api/](./docs/api/)

---

**📍 Navigate efficiently: Use this TOC as your starting point for any project interaction. Always check the SYSTEM_ARCHITECTURE.md lookup table before making changes.**