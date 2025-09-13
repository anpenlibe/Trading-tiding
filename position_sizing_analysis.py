#!/usr/bin/env python3
"""
Position Sizing Analysis - Demonstrates the critical bug

This script specifically tests how null stop_loss/target values
cause the risk manager to calculate oversized positions that
exceed capital limits.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.core.risk_manager import SimpleRiskManager
from src.data.config import INITIAL_CAPITAL, STOP_LOSS_PERCENT, TAKE_PROFIT_PERCENT


def demonstrate_position_sizing_bug():
    """Demonstrate how null stop_loss causes oversized positions."""
    print("🔍 Position Sizing Analysis - Demonstrating the Critical Bug")
    print("=" * 60)

    risk_manager = SimpleRiskManager()

    # Test scenario: RELIANCE at ₹2850
    symbol = "RELIANCE"
    entry_price = 2850.0
    capital = INITIAL_CAPITAL  # ₹10,000

    print(f"Test Scenario:")
    print(f"  Symbol: {symbol}")
    print(f"  Entry Price: ₹{entry_price:.2f}")
    print(f"  Available Capital: ₹{capital:.2f}")
    print(f"  Default Stop Loss %: {STOP_LOSS_PERCENT*100:.1f}%")
    print(f"  Default Take Profit %: {TAKE_PROFIT_PERCENT*100:.1f}%")

    print(f"\n🧪 TEST 1: With Proper Stop Loss (Expected Behavior)")
    print("-" * 50)

    # Calculate with proper stop loss
    proper_stop_loss = entry_price * (1 - STOP_LOSS_PERCENT)  # 2850 * 0.97 = 2764.5
    proper_target = entry_price * (1 + TAKE_PROFIT_PERCENT)   # 2850 * 1.05 = 2992.5

    try:
        risk_params_proper = risk_manager.calculate_risk_parameters(
            symbol=symbol,
            signal_type="BUY",
            entry_price=entry_price,
            capital=capital,
            stop_loss=proper_stop_loss,
            target=proper_target
        )

        print(f"  Stop Loss: ₹{proper_stop_loss:.2f}")
        print(f"  Target: ₹{proper_target:.2f}")
        print(f"  Stop Distance: ₹{abs(entry_price - proper_stop_loss):.2f}")
        print(f"  Position Size: {risk_params_proper.position_size} shares")
        print(f"  Position Value: ₹{risk_params_proper.position_value:.2f}")
        print(f"  Total Cost: ₹{risk_params_proper.total_cost:.2f}")
        print(f"  Risk Amount: ₹{risk_params_proper.risk_amount:.2f}")
        print(f"  Capital Usage: {(risk_params_proper.total_cost/capital)*100:.1f}%")

        # Validate this trade
        test_signal = {
            'symbol': symbol,
            'signal': 'BUY',
            'entry_price': entry_price,
            'stop_loss': proper_stop_loss,
            'target': proper_target,
            'available_capital': capital
        }

        is_valid, rejection_reason = risk_manager.validate_trade(test_signal, {})
        print(f"  Validation Result: {'✅ PASSED' if is_valid else '❌ REJECTED'}")
        if not is_valid:
            print(f"  Rejection Reason: {rejection_reason}")

    except Exception as e:
        print(f"  ❌ Error: {e}")

    print(f"\n🚨 TEST 2: With NULL Stop Loss (Current Bug)")
    print("-" * 50)

    try:
        risk_params_null = risk_manager.calculate_risk_parameters(
            symbol=symbol,
            signal_type="BUY",
            entry_price=entry_price,
            capital=capital,
            stop_loss=None,  # This is what AI returns!
            target=None      # This is what AI returns!
        )

        print(f"  Stop Loss: None (AI returns null)")
        print(f"  Target: None (AI returns null)")
        print(f"  Calculated Stop Loss: ₹{risk_params_null.stop_loss:.2f}")
        print(f"  Calculated Target: ₹{risk_params_null.target:.2f}")
        print(f"  Stop Distance: ₹{abs(entry_price - risk_params_null.stop_loss):.2f}")
        print(f"  Position Size: {risk_params_null.position_size} shares")
        print(f"  Position Value: ₹{risk_params_null.position_value:.2f}")
        print(f"  Total Cost: ₹{risk_params_null.total_cost:.2f}")
        print(f"  Risk Amount: ₹{risk_params_null.risk_amount:.2f}")
        print(f"  Capital Usage: {(risk_params_null.total_cost/capital)*100:.1f}%")

        # Validate this trade
        test_signal_null = {
            'symbol': symbol,
            'signal': 'BUY',
            'entry_price': entry_price,
            'stop_loss': None,  # AI bug!
            'target': None,     # AI bug!
            'available_capital': capital
        }

        is_valid_null, rejection_reason_null = risk_manager.validate_trade(test_signal_null, {})
        print(f"  Validation Result: {'✅ PASSED' if is_valid_null else '❌ REJECTED'}")
        if not is_valid_null:
            print(f"  Rejection Reason: {rejection_reason_null}")

        print(f"\n🔍 DETAILED ANALYSIS:")
        print(f"  Same parameters, different results:")
        print(f"  - Proper stop loss → {risk_params_proper.position_size} shares (₹{risk_params_proper.total_cost:.2f})")
        print(f"  - NULL stop loss → {risk_params_null.position_size} shares (₹{risk_params_null.total_cost:.2f})")
        print(f"  - Difference: {risk_params_null.position_size - risk_params_proper.position_size} shares")
        print(f"  - Cost difference: ₹{risk_params_null.total_cost - risk_params_proper.total_cost:.2f}")

    except Exception as e:
        print(f"  ❌ Error: {e}")

    print(f"\n🎯 ROOT CAUSE ANALYSIS")
    print("-" * 50)
    print("1. AI prompt template (prompt_builder.py lines 107-108) returns:")
    print('   "stop_loss": null, "target": null')
    print("\n2. Risk manager calculate_risk_parameters() uses defaults when null:")
    print(f"   stop_loss = entry_price * (1 - {STOP_LOSS_PERCENT}) = ₹{entry_price * (1 - STOP_LOSS_PERCENT):.2f}")
    print(f"   target = entry_price * (1 + {TAKE_PROFIT_PERCENT}) = ₹{entry_price * (1 + TAKE_PROFIT_PERCENT):.2f}")
    print("\n3. Position sizing formula: Risk Amount / Stop Distance")
    print(f"   Risk Amount = Capital * Risk% = ₹{capital} * 2% = ₹{capital * 0.02:.2f}")
    print(f"   Stop Distance = |Entry - Stop| = |₹{entry_price:.2f} - ₹{entry_price * (1 - STOP_LOSS_PERCENT):.2f}| = ₹{abs(entry_price - entry_price * (1 - STOP_LOSS_PERCENT)):.2f}")
    print(f"   Position Size = ₹{capital * 0.02:.2f} / ₹{abs(entry_price - entry_price * (1 - STOP_LOSS_PERCENT)):.2f} = {int((capital * 0.02) / abs(entry_price - entry_price * (1 - STOP_LOSS_PERCENT)))} shares")

    print(f"\n4. The calculated position requires:")
    print(f"   Total Cost = Position Size * Entry Price + Commission")
    print(f"   Total Cost = {int((capital * 0.02) / abs(entry_price - entry_price * (1 - STOP_LOSS_PERCENT)))} * ₹{entry_price:.2f} + ₹3.50")
    print(f"   Total Cost = ₹{int((capital * 0.02) / abs(entry_price - entry_price * (1 - STOP_LOSS_PERCENT))) * entry_price + 3.50:.2f}")

    capital_usage = (int((capital * 0.02) / abs(entry_price - entry_price * (1 - STOP_LOSS_PERCENT))) * entry_price + 3.50) / capital * 100
    print(f"\n5. Capital usage: {capital_usage:.1f}% > 20% limit → REJECTED")

    print(f"\n💡 THE FIX:")
    print("Either fix the AI prompt OR add null handling in risk manager")
    print("Option 1: Fix prompt_builder.py lines 107-108 to return calculated values")
    print("Option 2: Add fallback logic when stop_loss/target are null")


if __name__ == "__main__":
    demonstrate_position_sizing_bug()