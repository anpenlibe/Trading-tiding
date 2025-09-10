# CLAUDE CODE - PHASE 1 RESTRICTIONS

## YOU MUST:
1. Fix ONLY the 5 specific issues listed below
2. Test after EACH change
3. Document EVERY change
4. STOP if something breaks unexpectedly

## YOU MUST NOT:
- Add ANY new features
- Refactor ANY working code  
- Optimize ANYTHING
- Create new files (except documentation)
- Modify database files
- Change files not listed in the issues

## THE 5 FIXES TO MAKE:

### Fix 1: Paper Trader Validation
- File: src/paper_trader.py
- Method: _validate_trade() around line 450
- Remove: MAX_POSITION_SIZE check blocking small trades
- Keep: Capital sufficiency check
- Test: python -c "from src.paper_trader import PaperTrader; t=PaperTrader(1000); print(t.execute_simple_trade('TEST','BUY',10,10))"

### Fix 2: Test Configuration
- File: src/config.py
- Add at end: MIN_TRADE_VALUE_TEST = 100
- Add: TEST_MODE flag
- Document with comments

### Fix 3: Timestamp Parser
- File: src/data_collector.py
- Add method: _parse_timestamp to DataCollector class
- Handle: Multiple date formats
- Test: python -c "from src.data_collector import DataCollector; print('Import OK')"

### Fix 4: Import References
- Search: grep -r "ai_brain_optimized\|IndicatorCalculator" . --include="*.py"
- Replace: ai_brain_optimized → ai_brain
- Replace: IndicatorCalculator → indicator_engine functions

### Fix 5: Archive Cleanup
- Delete: archive/old_files/ directory
- Create: archive/ARCHIVED_FILES.md listing what was removed

## TESTING COMMANDS:
After all fixes, run:
1. python system_check.py
2. python tests/test_trading_session.py

## DOCUMENTATION:
Create/Update: docs/PHASE1_CHANGES.md with every change made
