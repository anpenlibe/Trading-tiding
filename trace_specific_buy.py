#!/usr/bin/env python3
"""
Trace a specific BUY signal through the execution pipeline
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def trace_buy_signal():
    """Trace what happens to a specific BUY signal"""
    print("=== Tracing Specific BUY Signal Execution ===")
    
    # Create a mock BUY signal like what AI generates
    mock_buy_signal = {
        'signal': 'BUY',
        'confidence': 0.85,
        'reasoning': 'Strong oversold conditions with RSI at 28.0',
        'entry_price': 1070.1,
        'stop_loss': 1054.05,
        'target': 1102.20,
        'position_size': 9,
        'risk_amount': 149.28
    }
    
    print(f"Mock BUY signal: {mock_buy_signal}")
    
    # Test the exact filtering condition from apps/backtest.py:348
    signal_value = mock_buy_signal.get('signal')
    print(f"signal.get('signal'): '{signal_value}'")
    print(f"signal.get('signal') != 'HOLD': {signal_value != 'HOLD'}")
    
    if signal_value != "HOLD":
        print("✅ Signal PASSES the filter check")
        
        # Test paper trader execution directly
        from src.core.paper_trader import PaperTrader
        trader = PaperTrader(initial_capital=100000.0)
        
        print(f"\nTesting direct paper trader execution...")
        current_price = 1070.10
        
        try:
            result = trader.execute_trade(mock_buy_signal, current_price)
            print(f"Direct execution result: {result}")
            
            if result.get('status') == 'EXECUTED':
                print("✅ Direct execution WORKS!")
            else:
                print(f"❌ Direct execution failed: {result.get('reason')}")
                
        except Exception as e:
            print(f"❌ Direct execution error: {e}")
        
        # Test risk manager validation
        print(f"\nTesting risk manager validation...")
        try:
            from src.core.risk_manager import SimpleRiskManager
            risk_manager = SimpleRiskManager()
            
            # Test validation
            account_info = trader.get_account_info()
            mock_buy_signal['available_capital'] = account_info['available_capital']
            
            current_positions = trader.get_positions()
            is_valid, rejection_reason = risk_manager.validate_trade(mock_buy_signal, current_positions)
            
            print(f"Risk validation result: valid={is_valid}, reason='{rejection_reason}'")
            
            if is_valid:
                print("✅ Risk validation PASSES")
                
                # Test risk parameter calculation
                risk_params = risk_manager.calculate_risk_parameters(
                    symbol='AXISBANK',
                    signal_type=mock_buy_signal['signal'],
                    entry_price=current_price,
                    capital=account_info['available_capital'],
                    stop_loss=mock_buy_signal.get('stop_loss'),
                    target=mock_buy_signal.get('target')
                )
                
                print(f"Risk parameters: {risk_params}")
                
                # Update signal with risk calculations
                mock_buy_signal.update({
                    'position_size': risk_params.position_size,
                    'stop_loss': risk_params.stop_loss,
                    'target': risk_params.target,
                    'entry_price': risk_params.entry_price,
                    'risk_amount': risk_params.risk_amount
                })
                
                print(f"Updated signal: {mock_buy_signal}")
                
                # Try execution again with updated signal
                final_result = trader.execute_trade(mock_buy_signal, current_price)
                print(f"Final execution result: {final_result}")
                
                if final_result.get('status') == 'EXECUTED':
                    print("🎉 COMPLETE PIPELINE SUCCESS!")
                else:
                    print(f"❌ Final execution failed: {final_result.get('reason')}")
                    
            else:
                print(f"❌ Risk validation FAILED: {rejection_reason}")
                
        except Exception as e:
            print(f"❌ Risk manager error: {e}")
    else:
        print("❌ Signal FAILS the filter check")

if __name__ == "__main__":
    trace_buy_signal()