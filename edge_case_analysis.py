#!/usr/bin/env python3
"""
Edge Case Analysis - Testing edge cases and failure scenarios

This script tests specific edge cases that cause the trading system to fail.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.core.risk_manager import SimpleRiskManager
from src.core.paper_trader import PaperTrader
from src.data.config import INITIAL_CAPITAL


def test_edge_cases():
    """Test various edge cases that cause system failures."""
    print("🔍 Edge Case Analysis - Testing Failure Scenarios")
    print("=" * 60)

    risk_manager = SimpleRiskManager()

    print("📋 EDGE CASE 1: High-priced stock with small capital")
    print("-" * 50)

    # Test with high-priced stock like MRF (₹1,20,000+)
    test_high_price_stock(risk_manager)

    print(f"\n📋 EDGE CASE 2: Very low stop loss distance")
    print("-" * 50)

    test_small_stop_distance(risk_manager)

    print(f"\n📋 EDGE CASE 3: Missing essential fields")
    print("-" * 50)

    test_missing_fields(risk_manager)

    print(f"\n📋 EDGE CASE 4: Paper trader with insufficient capital")
    print("-" * 50)

    test_insufficient_capital()

    print(f"\n📋 EDGE CASE 5: Zero or negative values")
    print("-" * 50)

    test_invalid_values(risk_manager)


def test_high_price_stock(risk_manager):
    """Test with high-priced stock."""
    capital = INITIAL_CAPITAL  # ₹10,000
    entry_price = 120000.0     # MRF-like price

    try:
        risk_params = risk_manager.calculate_risk_parameters(
            symbol="MRF",
            signal_type="BUY",
            entry_price=entry_price,
            capital=capital,
            stop_loss=None,  # Let it calculate
            target=None
        )

        print(f"  Stock: MRF @ ₹{entry_price:,.2f}")
        print(f"  Capital: ₹{capital:,.2f}")
        print(f"  Calculated Position Size: {risk_params.position_size} shares")
        print(f"  Position Value: ₹{risk_params.position_value:,.2f}")
        print(f"  Capital Usage: {(risk_params.position_value/capital)*100:.1f}%")

        # This should fail validation
        test_signal = {
            'symbol': 'MRF',
            'signal': 'BUY',
            'entry_price': entry_price,
            'stop_loss': None,
            'target': None,
            'available_capital': capital
        }

        is_valid, reason = risk_manager.validate_trade(test_signal, {})
        print(f"  Validation: {'✅ PASSED' if is_valid else '❌ REJECTED'}")
        if not is_valid:
            print(f"  Reason: {reason}")

    except Exception as e:
        print(f"  ❌ Error: {e}")


def test_small_stop_distance(risk_manager):
    """Test with very small stop loss distance."""
    capital = INITIAL_CAPITAL
    entry_price = 100.0
    stop_loss = 99.95  # Only 5 paisa stop loss

    try:
        risk_params = risk_manager.calculate_risk_parameters(
            symbol="TEST",
            signal_type="BUY",
            entry_price=entry_price,
            capital=capital,
            stop_loss=stop_loss,
            target=None
        )

        print(f"  Entry: ₹{entry_price:.2f}, Stop: ₹{stop_loss:.2f}")
        print(f"  Stop Distance: ₹{abs(entry_price - stop_loss):.2f}")
        print(f"  Position Size: {risk_params.position_size} shares")
        print(f"  Position Value: ₹{risk_params.position_value:,.2f}")

        if risk_params.position_value > capital:
            print(f"  ⚠️ Position exceeds capital by ₹{risk_params.position_value - capital:.2f}")

    except Exception as e:
        print(f"  ❌ Error: {e}")


def test_missing_fields(risk_manager):
    """Test with missing essential fields."""
    test_cases = [
        {
            'name': 'Missing entry_price',
            'signal': {
                'symbol': 'TEST',
                'signal': 'BUY',
                'available_capital': 10000
                # entry_price missing
            }
        },
        {
            'name': 'Missing symbol',
            'signal': {
                'signal': 'BUY',
                'entry_price': 100,
                'available_capital': 10000
                # symbol missing
            }
        },
        {
            'name': 'Missing available_capital',
            'signal': {
                'symbol': 'TEST',
                'signal': 'BUY',
                'entry_price': 100
                # available_capital missing
            }
        }
    ]

    for test_case in test_cases:
        print(f"    Testing: {test_case['name']}")
        try:
            is_valid, reason = risk_manager.validate_trade(test_case['signal'], {})
            print(f"      Result: {'✅ PASSED' if is_valid else '❌ REJECTED'}")
            if not is_valid:
                print(f"      Reason: {reason}")
        except Exception as e:
            print(f"      ❌ Error: {e}")


def test_insufficient_capital():
    """Test paper trader with insufficient capital."""
    trader = PaperTrader(initial_capital=1000)  # Small capital

    signal = {
        'symbol': 'RELIANCE',
        'signal': 'BUY',
        'confidence': 0.8,
        'position_size': 10,  # Large position
        'stop_loss': 2800,
        'target': 2950,
        'reasoning': 'Testing insufficient capital'
    }

    result = trader.execute_trade(signal, current_price=2850)

    print(f"  Capital: ₹1,000")
    print(f"  Requested: RELIANCE x10 @ ₹2,850")
    print(f"  Required: ₹{10 * 2850 + 3.5:,.2f}")
    print(f"  Result: {result.get('status')}")
    if result.get('status') == 'REJECTED':
        print(f"  Reason: {result.get('reason')}")


def test_invalid_values(risk_manager):
    """Test with zero or negative values."""
    test_cases = [
        {'name': 'Zero price', 'entry_price': 0, 'expected': 'ERROR'},
        {'name': 'Negative price', 'entry_price': -100, 'expected': 'ERROR'},
        {'name': 'Zero stop distance', 'entry_price': 100, 'stop_loss': 100, 'expected': 'ERROR'},
    ]

    for test_case in test_cases:
        print(f"    Testing: {test_case['name']}")
        try:
            risk_params = risk_manager.calculate_risk_parameters(
                symbol="TEST",
                signal_type="BUY",
                entry_price=test_case['entry_price'],
                capital=10000,
                stop_loss=test_case.get('stop_loss'),
                target=None
            )
            print(f"      ⚠️ Unexpected success: Position size {risk_params.position_size}")
        except Exception as e:
            print(f"      ✅ Correctly failed: {e}")


def analyze_real_trading_scenarios():
    """Analyze realistic trading scenarios."""
    print(f"\n🎯 REAL TRADING SCENARIOS")
    print("=" * 60)

    risk_manager = SimpleRiskManager()

    # Realistic scenarios based on Indian stock market
    scenarios = [
        {
            'name': 'RELIANCE - Swing Trade',
            'symbol': 'RELIANCE',
            'price': 2850,
            'capital': 10000,
            'expected_position': '2-3 shares'
        },
        {
            'name': 'SBIN - Bank Stock',
            'symbol': 'SBIN',
            'price': 650,
            'capital': 10000,
            'expected_position': '7-8 shares'
        },
        {
            'name': 'INFY - IT Stock',
            'symbol': 'INFY',
            'price': 1650,
            'capital': 10000,
            'expected_position': '3-4 shares'
        }
    ]

    for scenario in scenarios:
        print(f"\n📊 {scenario['name']}")
        print("-" * 30)

        try:
            # Test with AI-like signal (null stop/target)
            risk_params = risk_manager.calculate_risk_parameters(
                symbol=scenario['symbol'],
                signal_type="BUY",
                entry_price=scenario['price'],
                capital=scenario['capital'],
                stop_loss=None,  # AI bug
                target=None      # AI bug
            )

            print(f"  Price: ₹{scenario['price']:,.2f}")
            print(f"  Capital: ₹{scenario['capital']:,.2f}")
            print(f"  Position Size: {risk_params.position_size} shares")
            print(f"  Position Value: ₹{risk_params.position_value:,.2f}")
            print(f"  Capital Usage: {(risk_params.position_value/scenario['capital'])*100:.1f}%")
            print(f"  Expected: {scenario['expected_position']}")

            # Validate
            test_signal = {
                'symbol': scenario['symbol'],
                'signal': 'BUY',
                'entry_price': scenario['price'],
                'stop_loss': None,
                'target': None,
                'available_capital': scenario['capital']
            }

            is_valid, reason = risk_manager.validate_trade(test_signal, {})
            print(f"  Validation: {'✅ PASSED' if is_valid else '❌ REJECTED'}")
            if not is_valid:
                print(f"  Rejection: {reason}")

        except Exception as e:
            print(f"  ❌ Error: {e}")


if __name__ == "__main__":
    test_edge_cases()
    analyze_real_trading_scenarios()