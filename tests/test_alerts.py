"""Test alert system."""

import pytest
from datetime import datetime, timedelta
from src.alerts.alert_engine import AlertEngine, AlertType
from src.alerts.rules import PriceCrossRule, RSIExtremeRule, VolumeSpikRule, MACDCrossRule


def test_alert_engine():
    """Test basic alert engine functionality."""
    engine = AlertEngine()
    rule = PriceCrossRule("TEST", 100.0, "above")
    engine.add_rule(rule)
    
    # Test no trigger
    data = {"symbol": "TEST", "close": 99.0}
    alerts = engine.check_conditions(data)
    assert len(alerts) == 0
    
    # Test trigger
    data = {"symbol": "TEST", "close": 101.0}
    alerts = engine.check_conditions(data)
    assert len(alerts) == 1
    assert alerts[0].type == AlertType.PRICE_CROSS
    assert alerts[0].symbol == "TEST"
    
    print("✅ Basic alert engine tests pass")


def test_price_cross_rule():
    """Test price crossover detection."""
    rule = PriceCrossRule("TEST", 100.0, "above")
    
    # No trigger on first data point
    data = {"symbol": "TEST", "close": 99.0}
    assert not rule.check(data)
    
    # Should trigger on crossover
    data = {"symbol": "TEST", "close": 101.0}
    assert rule.check(data)
    
    # Should not trigger again on same side
    data = {"symbol": "TEST", "close": 102.0}
    assert not rule.check(data)
    
    print("✅ Price cross rule tests pass")


def test_rsi_extreme_rule():
    """Test RSI extreme detection."""
    rule = RSIExtremeRule("TEST", overbought=70, oversold=30)
    
    # No trigger in normal range
    data = {"symbol": "TEST", "indicators": {"rsi_14": 50}}
    assert not rule.check(data)
    
    # Trigger on overbought
    data = {"symbol": "TEST", "indicators": {"rsi_14": 75}}
    assert rule.check(data)
    
    # Trigger on oversold
    data = {"symbol": "TEST", "indicators": {"rsi_14": 25}}
    assert rule.check(data)
    
    print("✅ RSI extreme rule tests pass")


def test_volume_spike_rule():
    """Test volume spike detection."""
    rule = VolumeSpikRule("TEST", spike_multiplier=2.0)
    
    # Build volume history (no trigger until enough data)
    for i in range(19):
        data = {"symbol": "TEST", "volume": 1000}
        assert not rule.check(data)
    
    # Normal volume - no trigger
    data = {"symbol": "TEST", "volume": 1000}
    assert not rule.check(data)
    
    # Volume spike - should trigger
    data = {"symbol": "TEST", "volume": 2500}
    assert rule.check(data)
    
    print("✅ Volume spike rule tests pass")


def test_macd_cross_rule():
    """Test MACD crossover detection."""
    rule = MACDCrossRule("TEST", direction="bullish")
    
    # No trigger on first data point
    data = {"symbol": "TEST", "indicators": {"macd": -1, "macd_signal": 0}}
    assert not rule.check(data)
    
    # Should trigger on bullish crossover
    data = {"symbol": "TEST", "indicators": {"macd": 1, "macd_signal": 0}}
    assert rule.check(data)
    
    # Should not trigger when already above
    data = {"symbol": "TEST", "indicators": {"macd": 2, "macd_signal": 0}}
    assert not rule.check(data)
    
    print("✅ MACD cross rule tests pass")


def test_alert_cooldowns():
    """Test alert cooldown functionality."""
    engine = AlertEngine()
    rule = PriceCrossRule("TEST", 100.0, "above")
    rule.cooldown_minutes = 1  # 1 minute cooldown
    engine.add_rule(rule)
    
    # Set initial price below threshold
    data = {"symbol": "TEST", "close": 99.0}
    alerts = engine.check_conditions(data)
    assert len(alerts) == 0
    
    # First trigger - crossover
    data = {"symbol": "TEST", "close": 101.0}
    alerts = engine.check_conditions(data)
    assert len(alerts) == 1
    
    # Should be in cooldown - try to trigger again
    data = {"symbol": "TEST", "close": 99.0}  # Reset price
    engine.check_conditions(data)
    data = {"symbol": "TEST", "close": 101.0}  # Try to trigger again
    alerts = engine.check_conditions(data)
    assert len(alerts) == 0  # Should be blocked by cooldown
    
    # Manually expire cooldown
    engine.cooldowns[rule.name] = datetime.now() - timedelta(minutes=2)
    
    # Should trigger again after cooldown
    data = {"symbol": "TEST", "close": 99.0}  # Reset price
    engine.check_conditions(data)
    data = {"symbol": "TEST", "close": 101.0}  # Trigger again
    alerts = engine.check_conditions(data)
    assert len(alerts) == 1
    
    print("✅ Alert cooldown tests pass")


def test_alert_callbacks():
    """Test alert callback system."""
    engine = AlertEngine()
    triggered_alerts = []
    
    def test_callback(alert):
        triggered_alerts.append(alert)
    
    engine.register_callback(AlertType.PRICE_CROSS, test_callback)
    
    rule = PriceCrossRule("TEST", 100.0, "above")
    engine.add_rule(rule)
    
    # Set initial price below threshold
    data = {"symbol": "TEST", "close": 99.0}
    engine.check_conditions(data)
    
    # Trigger alert - crossover
    data = {"symbol": "TEST", "close": 101.0}
    engine.check_conditions(data)
    
    # Check callback was called
    assert len(triggered_alerts) == 1
    assert triggered_alerts[0].type == AlertType.PRICE_CROSS
    
    print("✅ Alert callback tests pass")


def test_alert_metadata():
    """Test alert metadata generation."""
    rule = RSIExtremeRule("TEST")
    data = {"symbol": "TEST", "indicators": {"rsi_14": 75}}
    
    # Get metadata
    metadata = rule.get_metadata(data)
    
    assert "rsi_value" in metadata
    assert "condition" in metadata
    assert metadata["rsi_value"] == 75
    assert metadata["condition"] == "overbought"
    
    print("✅ Alert metadata tests pass")


def test_multiple_symbols():
    """Test alerts with multiple symbols."""
    engine = AlertEngine()
    
    # Add rules for different symbols
    rule1 = PriceCrossRule("SYMBOL1", 100.0, "above")
    rule2 = PriceCrossRule("SYMBOL2", 200.0, "above")
    engine.add_rule(rule1)
    engine.add_rule(rule2)
    
    # Set initial prices below thresholds
    data = {"symbol": "SYMBOL1", "close": 99.0}
    engine.check_conditions(data)
    data = {"symbol": "SYMBOL2", "close": 199.0}
    engine.check_conditions(data)
    
    # Trigger only SYMBOL1
    data = {"symbol": "SYMBOL1", "close": 101.0}
    alerts = engine.check_conditions(data)
    assert len(alerts) == 1
    assert alerts[0].symbol == "SYMBOL1"
    
    # Trigger only SYMBOL2
    data = {"symbol": "SYMBOL2", "close": 201.0}
    alerts = engine.check_conditions(data)
    assert len(alerts) == 1
    assert alerts[0].symbol == "SYMBOL2"
    
    print("✅ Multiple symbol tests pass")


def run_all_tests():
    """Run all alert system tests."""
    print("🧪 Running Alert System Tests")
    print("=" * 40)
    
    try:
        test_alert_engine()
        test_price_cross_rule()
        test_rsi_extreme_rule()
        test_volume_spike_rule()
        test_macd_cross_rule()
        test_alert_cooldowns()
        test_alert_callbacks()
        test_alert_metadata()
        test_multiple_symbols()
        
        print("\n🎉 All alert system tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)