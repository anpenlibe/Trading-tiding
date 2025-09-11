# 🔧 Claude Code Development Rules & Guidelines

**Comprehensive Development Standards for the Claude AI Trading System**  
**Purpose**: Ensure consistent, maintainable, and high-quality code across all development  
**Scope**: All development work using Claude Code IDE and AI-assisted coding  

---

## 🎯 Core Development Principles

### **1. Architecture-First Development**
- **Always consult [SYSTEM_ARCHITECTURE.md](./SYSTEM_ARCHITECTURE.md) before making changes**
- Use the Change Impact Matrix to identify all affected components
- Update the architecture document FIRST, then implement changes
- Follow dependency chains to avoid breaking changes

### **2. Documentation-Driven Development**
- **Document before coding**: Update README files before implementation
- **Code comments**: Minimal comments, let code be self-documenting
- **API documentation**: Auto-generate from docstrings using generate_docs.py
- **Architecture updates**: Keep SYSTEM_ARCHITECTURE.md current

### **3. Test-Driven Quality**
- **Write tests first**: Define expected behavior before implementation
- **Maintain coverage**: Target >90% coverage on critical modules
- **Run tests frequently**: Use `python run_tests.py` during development
- **Integration testing**: Test component interactions, not just units

---

## 📋 File Organization Standards

### **Directory Structure Rules**
```
# ALWAYS follow this structure - DO NOT deviate:
apps/           ← Executable applications only
src/core/       ← Business logic (AI, risk, trading)
src/data/       ← Data handling and configuration  
src/ai/         ← AI components and prompt engineering
src/alerts/     ← Alert system modules
src/monitoring/ ← Performance and error tracking
src/utils/      ← Utility functions and helpers
tests/          ← All testing code
docs/           ← Documentation (auto-generated and manual)
```

### **File Naming Conventions**
- **Python modules**: `snake_case.py` (e.g., `ai_brain.py`, `risk_manager.py`)
- **Classes**: `PascalCase` (e.g., `ClaudeAI`, `RiskManager`, `PaperTrader`)
- **Functions/methods**: `snake_case()` (e.g., `calculate_risk()`, `execute_trade()`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `MAX_RISK_PER_TRADE`, `SYMBOLS`)
- **README files**: Always `README.md` (uppercase)

### **Import Organization**
```python
# Standard library imports
import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional

# Third-party imports
import pandas as pd
import numpy as np
from anthropic import Anthropic

# Internal imports (relative to project root)
from src.core.ai_brain import ClaudeAI
from src.core.risk_manager import SimpleRiskManager
from src.data.config import SYMBOLS, INITIAL_CAPITAL
from src.interfaces import BaseDecisionModel, TradingSignal
from src.utils.logger import setup_logger
```

---

## 🏗️ Code Architecture Rules

### **Interface-Driven Design**
- **Always implement interfaces**: Use base classes from `src/interfaces.py`
- **Contract compliance**: Implement ALL abstract methods
- **Type hints**: Use type annotations consistently
- **Polymorphism**: Design for multiple implementations

```python
# GOOD: Implements interface
from src.interfaces import BaseDecisionModel

class ClaudeAI(BaseDecisionModel):
    def analyze(self, market_data: pd.DataFrame, indicators: Dict[str, float]) -> Dict[str, Any]:
        # Implementation here
        pass

# BAD: No interface implementation
class ClaudeAI:
    def analyze(self, data, indicators):  # No type hints
        # Implementation here
        pass
```

### **Configuration Management**
- **Centralized config**: ALL configuration in `src/data/config.py`
- **Environment variables**: Use `.env` file for secrets and overrides
- **No hardcoding**: NEVER hardcode values in business logic
- **Validation**: Validate configuration on startup

```python
# GOOD: Use centralized config
from src.data.config import MAX_RISK_PER_TRADE, ANTHROPIC_API_KEY

def calculate_risk(capital: float) -> float:
    return capital * MAX_RISK_PER_TRADE

# BAD: Hardcoded values
def calculate_risk(capital: float) -> float:
    return capital * 0.015  # Magic number!
```

### **Error Handling Strategy**
- **Explicit error handling**: Handle specific exceptions
- **Graceful degradation**: System should continue operating when possible
- **Comprehensive logging**: Log all errors with context
- **User-friendly messages**: Provide actionable error messages

```python
# GOOD: Specific error handling
from src.exceptions import AIAnalysisError, ConfigurationError

try:
    decision = self.ai_brain.analyze(data, indicators)
except AIAnalysisError as e:
    logger.error(f"AI analysis failed: {e}")
    return {'signal': 'HOLD', 'reason': 'AI analysis unavailable'}
except ConfigurationError as e:
    logger.critical(f"Configuration error: {e}")
    raise  # Critical errors should propagate

# BAD: Generic error handling  
try:
    decision = self.ai_brain.analyze(data, indicators)
except Exception as e:
    print(f"Error: {e}")  # No context, poor logging
    return None  # Unclear what None means
```

---

## 📝 Documentation Standards

### **Docstring Requirements**
```python
def calculate_risk_parameters(
    self,
    symbol: str,
    signal_type: str,
    entry_price: float,
    capital: float,
    stop_loss: Optional[float] = None,
    target: Optional[float] = None
) -> RiskParameters:
    """
    Calculate comprehensive risk parameters for a trading signal.
    
    Args:
        symbol: Stock symbol (e.g., 'RELIANCE')
        signal_type: Trading signal ('BUY' or 'SELL')
        entry_price: Intended entry price for the trade
        capital: Available capital for position sizing
        stop_loss: Optional stop loss price (calculated if not provided)
        target: Optional target price (calculated if not provided)
    
    Returns:
        RiskParameters object containing:
        - position_size: Number of shares to trade
        - risk_amount: Total capital at risk (₹)
        - reward_amount: Expected reward (₹)
        - risk_reward_ratio: Reward/risk ratio
        - stop_loss: Final stop loss price
        - target: Final target price
    
    Raises:
        ValueError: If entry_price <= 0 or capital <= 0
        RiskManagerError: If risk parameters violate trading rules
    
    Example:
        >>> risk_mgr = SimpleRiskManager()
        >>> params = risk_mgr.calculate_risk_parameters(
        ...     "RELIANCE", "BUY", 2850.0, 10000.0
        ... )
        >>> params.position_size
        35
    """
```

### **README File Standards**
Each README.md must include:
1. **Purpose**: What the directory/module does
2. **Key Components**: Main classes, functions, or applications
3. **Usage Examples**: Code examples with expected outputs
4. **Dependencies**: Internal and external dependencies
5. **Configuration**: Required environment variables or settings
6. **Related Documentation**: Links to other relevant docs

### **Code Comments Policy**
- **NO comments for obvious code**: Let code be self-documenting
- **Complex logic only**: Comment WHY, not WHAT
- **Business logic**: Comment regulatory or domain-specific rules
- **Temporary code**: Mark with TODO, FIXME, or HACK

```python
# GOOD: Explains business logic
# Kelly Criterion: Optimal position size = (bp - q) / b
# where b = odds received, p = probability of win, q = probability of loss
position_size = (win_prob * avg_return - loss_prob) / avg_return

# BAD: Obvious comments
x = x + 1  # Increment x by 1
if condition:  # Check if condition is true
    return True  # Return True
```

---

## 🧪 Testing Standards

### **Test Organization**
```
tests/
├── conftest.py              ← Shared fixtures (REQUIRED)
├── unit/                    ← Isolated component tests
│   ├── test_ai_brain.py    ← One test file per module
│   └── test_risk_manager.py
├── integration/             ← Component interaction tests
│   ├── test_trading_flow.py ← End-to-end workflows
│   └── test_data_pipeline.py
└── test_alerts.py          ← System-specific tests
```

### **Test Writing Rules**
```python
def test_component_function_scenario():
    """Test naming: test_[component]_[function]_[scenario]"""
    # Arrange: Set up test data
    risk_manager = SimpleRiskManager()
    signal = {'signal': 'BUY', 'confidence': 0.8}
    
    # Act: Execute the function
    result = risk_manager.validate_trade(signal, positions)
    
    # Assert: Verify expected outcome
    assert result[0] is True  # Trade approved
    assert "sufficient capital" in result[1]  # Reason provided

def test_risk_manager_calculate_position_size_insufficient_capital():
    """Descriptive test names for edge cases"""
    # Test specific edge case with clear naming
    pass

# Use fixtures from conftest.py
def test_ai_decision_with_sample_data(sample_market_data, mock_claude_api):
    """Leverage shared fixtures for consistency"""
    ai = ClaudeAI()
    decision = ai.analyze(sample_market_data, indicators)
    
    assert decision['signal'] in ['BUY', 'SELL', 'HOLD']
    assert 0 <= decision['confidence'] <= 1
```

### **Test Coverage Requirements**
- **Critical modules**: >95% coverage (ai_brain, risk_manager, paper_trader)
- **Integration modules**: >90% coverage (data_collector, trading flows)
- **Utility modules**: >85% coverage (config, logger, alerts)
- **Overall project**: >90% coverage

```bash
# Check coverage regularly
python run_tests.py --coverage

# HTML report for detailed analysis
pytest --cov=src --cov-report=html
open htmlcov/index.html
```

---

## 🚀 Development Workflow

### **Feature Development Process**
1. **Planning Phase**
   - Check [SYSTEM_ARCHITECTURE.md](./SYSTEM_ARCHITECTURE.md) for impact analysis
   - Update architecture document with planned changes
   - Create/update relevant README files
   - Plan test coverage

2. **Implementation Phase**
   - Write failing tests first (TDD approach)
   - Implement minimal code to pass tests
   - Follow interface contracts and type hints
   - Use centralized configuration

3. **Integration Phase**
   - Run full test suite: `python run_tests.py`
   - Check system health: `python apps/health_check.py`
   - Update integration tests if needed
   - Verify no breaking changes

4. **Documentation Phase**
   - Update docstrings and type hints
   - Update README files for changed modules
   - Regenerate API docs: `python generate_docs.py`
   - Update SYSTEM_ARCHITECTURE.md if needed

### **Bug Fix Process**
1. **Identify the Issue**
   - Use SYSTEM_ARCHITECTURE.md to find related components
   - Check test coverage for the problematic module
   - Review logs and error messages

2. **Reproduce the Bug**
   - Write a failing test that reproduces the issue
   - Isolate the problem to specific component
   - Verify bug affects expected functionality

3. **Fix and Verify**
   - Implement minimal fix to pass the test
   - Run full test suite to check for regressions
   - Test fix in realistic scenarios

4. **Document the Fix**
   - Update relevant documentation
   - Add test case to prevent regression
   - Update changelog if user-facing

---

## 📊 Performance Standards

### **Code Performance Rules**
- **Database operations**: Use batch operations, proper indexing
- **API calls**: Implement caching, rate limiting, retry logic
- **Memory usage**: Clean up resources, avoid memory leaks
- **CPU optimization**: Use vectorized operations (numpy/pandas)

```python
# GOOD: Batch database operations
def insert_multiple_records(self, records: List[Dict]):
    query = "INSERT INTO price_data (symbol, timestamp, close) VALUES (?, ?, ?)"
    data = [(r['symbol'], r['timestamp'], r['close']) for r in records]
    self.conn.executemany(query, data)

# BAD: Individual database operations
def insert_multiple_records(self, records: List[Dict]):
    for record in records:
        query = f"INSERT INTO price_data VALUES ('{record['symbol']}', ...)"
        self.conn.execute(query)  # SQL injection risk + slow
```

### **Resource Management**
- **File handles**: Always use context managers (`with` statements)
- **Database connections**: Proper connection pooling and cleanup
- **API clients**: Reuse connections, handle timeouts
- **Memory**: Clean up large objects, use generators for large datasets

```python
# GOOD: Proper resource management
def process_large_dataset(self, file_path: str):
    with open(file_path, 'r') as f:
        for line in f:  # Generator - memory efficient
            yield self.process_line(line)

# BAD: Resource leaks
def process_large_dataset(self, file_path: str):
    f = open(file_path, 'r')  # No cleanup
    data = f.readlines()  # Loads entire file into memory
    return [self.process_line(line) for line in data]
```

---

## 🔒 Security Standards

### **API Key Management**
- **Environment variables**: Store ALL secrets in `.env` file
- **No hardcoding**: NEVER commit API keys to code
- **Validation**: Validate API keys on startup
- **Error messages**: Don't expose API keys in error messages

```python
# GOOD: Secure API key handling
from src.data.config import ANTHROPIC_API_KEY

class ClaudeAI:
    def __init__(self):
        if not ANTHROPIC_API_KEY:
            raise ConfigurationError("ANTHROPIC_API_KEY not configured")
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# BAD: Hardcoded API key
class ClaudeAI:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key="sk-ant-api03-xyz...")  # NEVER!
```

### **Data Validation**
- **Input validation**: Validate all external inputs
- **Type checking**: Use type hints and runtime validation
- **SQL injection**: Use parameterized queries ALWAYS
- **Data sanitization**: Clean data before processing

```python
# GOOD: Input validation
def calculate_position_size(self, capital: float, risk_percent: float) -> int:
    if capital <= 0:
        raise ValueError("Capital must be positive")
    if not (0 < risk_percent <= 1):
        raise ValueError("Risk percent must be between 0 and 1")
    
    return int(capital * risk_percent)

# BAD: No validation
def calculate_position_size(self, capital, risk_percent):
    return capital * risk_percent  # Could return negative or huge values
```

---

## 🔧 Claude Code IDE Integration

### **Claude Code Specific Rules**
- **Documentation**: Use Claude to generate initial docstrings, then refine
- **Code review**: Use Claude for code review before committing
- **Test generation**: Use Claude to suggest test cases, then implement
- **Refactoring**: Use Claude for refactoring suggestions, validate manually

### **AI-Assisted Development Best Practices**
1. **Clear prompts**: Be specific about requirements and constraints
2. **Validate AI suggestions**: Never blindly accept AI-generated code
3. **Test AI code**: All AI-generated code must have tests
4. **Human oversight**: Review all AI suggestions for security and correctness

### **Prompt Templates for Common Tasks**
```
# Code review prompt:
"Review this Python code for the trading system. Check for:
- Interface compliance with src/interfaces.py
- Error handling and logging
- Performance considerations
- Security issues (API keys, SQL injection)
- Code style consistency with existing codebase"

# Test generation prompt:
"Generate pytest unit tests for this function. Include:
- Happy path scenarios
- Edge cases (boundary conditions)
- Error conditions
- Use fixtures from conftest.py
- Follow AAA pattern (Arrange, Act, Assert)"
```

---

## 📈 Monitoring and Maintenance

### **Code Quality Monitoring**
```bash
# Regular quality checks
python run_tests.py --coverage  # Weekly
python apps/health_check.py     # Daily
python optimize_system.py       # Weekly

# Code analysis tools
flake8 src/                     # Style checking
mypy src/                       # Type checking
bandit -r src/                  # Security scanning
```

### **Performance Monitoring**
- **Execution time**: Monitor critical function performance
- **Memory usage**: Track memory consumption patterns
- **API response times**: Monitor external API performance
- **Database query performance**: Optimize slow queries

### **Documentation Maintenance**
- **Weekly**: Update module README files for any changes
- **Monthly**: Review and update SYSTEM_ARCHITECTURE.md
- **Per release**: Regenerate API documentation
- **Quarterly**: Full documentation audit and cleanup

---

## 🎯 Quality Gates

### **Pre-Commit Checklist**
- [ ] All tests pass: `python run_tests.py`
- [ ] Coverage maintained: >90% overall
- [ ] System health check passes: `python apps/health_check.py`
- [ ] Documentation updated: README files current
- [ ] Type hints present: All public methods have type hints
- [ ] No hardcoded values: Configuration centralized
- [ ] Error handling implemented: Graceful failure handling

### **Pre-Release Checklist**
- [ ] Full test suite passes
- [ ] Integration tests validate workflows
- [ ] Performance benchmarks maintained
- [ ] Security scan clean (no hardcoded secrets)
- [ ] Documentation complete and accurate
- [ ] API documentation generated
- [ ] Architecture document updated
- [ ] Changelog updated with user-facing changes

---

## 🚨 Common Pitfalls to Avoid

### **Architecture Violations**
- ❌ **Circular imports**: Don't create import cycles
- ❌ **Direct database access**: Use DataCollector for all data operations
- ❌ **Bypassing interfaces**: Always implement base classes
- ❌ **Hardcoded paths**: Use relative imports and configuration

### **Testing Antipatterns**
- ❌ **Testing implementation details**: Test behavior, not internal methods
- ❌ **Brittle tests**: Tests that break on irrelevant changes
- ❌ **No error testing**: Not testing error conditions and edge cases
- ❌ **Large test files**: Split large test files by functionality

### **Performance Problems**
- ❌ **N+1 queries**: Batch database operations
- ❌ **Memory leaks**: Properly close resources
- ❌ **Blocking operations**: Use async for I/O-bound operations
- ❌ **Inefficient data structures**: Choose appropriate data types

---

## 🔗 Related Documentation

### **Essential Reading**
- **[SYSTEM_ARCHITECTURE.md](./SYSTEM_ARCHITECTURE.md)**: Architecture and change impact analysis
- **[PROJECT_TOC.md](./PROJECT_TOC.md)**: Navigation and documentation hierarchy
- **[README.md](./README.md)**: User-focused project overview

### **Module-Specific Guidelines**
- **[apps/README.md](./apps/README.md)**: Application development standards
- **[src/core/README.md](./src/core/README.md)**: Core business logic standards
- **[src/data/README.md](./src/data/README.md)**: Data handling and configuration
- **[tests/README.md](./tests/README.md)**: Testing standards and practices

---

## 📝 Rule Updates and Evolution

### **Rule Modification Process**
1. **Propose changes**: Discuss significant rule changes
2. **Update this document**: Modify rules with rationale
3. **Communicate changes**: Notify all developers
4. **Update tooling**: Modify linting rules, CI/CD as needed

### **Regular Review**
- **Monthly**: Review rules effectiveness
- **Quarterly**: Update based on lessons learned
- **Per release**: Ensure rules align with current architecture

---

**🎯 These rules ensure consistent, maintainable, and high-quality development. Follow them rigorously to maintain system integrity and development efficiency.**

**📋 When in doubt, consult [SYSTEM_ARCHITECTURE.md](./SYSTEM_ARCHITECTURE.md) for change impact analysis and [PROJECT_TOC.md](./PROJECT_TOC.md) for navigation guidance.**