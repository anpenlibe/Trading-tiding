"""Alert monitoring dashboard."""

from typing import Dict, Any
from datetime import datetime
from src.alerts.alert_engine import AlertEngine, AlertType


def display_alert_status(alert_engine: AlertEngine):
    """Display current alert status."""
    print("\n" + "="*60)
    print("ALERT SYSTEM STATUS")
    print("="*60)
    
    print(f"\nActive Rules: {len(alert_engine.alert_rules)}")
    print(f"Cooldowns Active: {len(alert_engine.cooldowns)}")
    
    # Group rules by type
    by_type = {}
    for rule in alert_engine.alert_rules:
        if rule.alert_type not in by_type:
            by_type[rule.alert_type] = []
        by_type[rule.alert_type].append(rule)
    
    for alert_type, rules in by_type.items():
        print(f"\n{alert_type.value}: {len(rules)} rules")
        for rule in rules[:3]:  # Show first 3
            print(f"  - {rule.name}")
        if len(rules) > 3:
            print(f"  ... and {len(rules) - 3} more")


def display_alert_rules(alert_engine: AlertEngine, symbol: str = None):
    """Display detailed alert rules information."""
    print("\n" + "="*60)
    print("ALERT RULES CONFIGURATION")
    print("="*60)
    
    rules_to_show = alert_engine.alert_rules
    if symbol:
        rules_to_show = [r for r in alert_engine.alert_rules if symbol in r.name]
        print(f"Showing rules for symbol: {symbol}")
    
    if not rules_to_show:
        print("No rules found.")
        return
    
    # Group by symbol
    by_symbol = {}
    for rule in rules_to_show:
        # Extract symbol from rule name
        rule_symbol = rule.name.split('_')[0]
        if rule_symbol not in by_symbol:
            by_symbol[rule_symbol] = []
        by_symbol[rule_symbol].append(rule)
    
    for sym, rules in by_symbol.items():
        print(f"\n📊 {sym}:")
        for rule in rules:
            cooldown_status = ""
            if rule.name in alert_engine.cooldowns:
                remaining = alert_engine.cooldowns[rule.name] - datetime.now()
                if remaining.total_seconds() > 0:
                    cooldown_status = f" (cooldown: {remaining.total_seconds():.0f}s)"
            
            print(f"  • {rule.alert_type.value}: {rule.condition} "
                  f"(threshold: {rule.threshold}, priority: {rule.priority}){cooldown_status}")


def display_alert_history(triggered_alerts: list):
    """Display recent alert history."""
    print("\n" + "="*60)
    print("RECENT ALERT HISTORY")
    print("="*60)
    
    if not triggered_alerts:
        print("No recent alerts.")
        return
    
    # Sort by timestamp (most recent first)
    sorted_alerts = sorted(triggered_alerts, key=lambda x: x.triggered_at, reverse=True)
    
    for alert in sorted_alerts[:10]:  # Show last 10 alerts
        time_str = alert.triggered_at.strftime("%H:%M:%S")
        print(f"[{time_str}] {alert.symbol} - {alert.type.value}")
        print(f"    Condition: {alert.condition}")
        print(f"    Value: {alert.current_value:.2f} (threshold: {alert.threshold:.2f})")
        print(f"    Priority: {alert.priority}")
        if alert.metadata:
            key_info = []
            for key, value in alert.metadata.items():
                if isinstance(value, (int, float)):
                    key_info.append(f"{key}: {value:.2f}")
                else:
                    key_info.append(f"{key}: {value}")
            if key_info:
                print(f"    Info: {', '.join(key_info[:3])}")  # Show first 3 metadata items
        print()


def get_alert_summary(alert_engine: AlertEngine) -> Dict[str, Any]:
    """Get alert system summary statistics."""
    summary = {
        'total_rules': len(alert_engine.alert_rules),
        'active_cooldowns': len(alert_engine.cooldowns),
        'rules_by_type': {},
        'rules_by_symbol': {},
        'callback_registrations': len(alert_engine.callbacks)
    }
    
    # Count by type
    for rule in alert_engine.alert_rules:
        alert_type = rule.alert_type.value
        if alert_type not in summary['rules_by_type']:
            summary['rules_by_type'][alert_type] = 0
        summary['rules_by_type'][alert_type] += 1
    
    # Count by symbol
    for rule in alert_engine.alert_rules:
        # Extract symbol from rule name
        symbol = rule.name.split('_')[0]
        if symbol not in summary['rules_by_symbol']:
            summary['rules_by_symbol'][symbol] = 0
        summary['rules_by_symbol'][symbol] += 1
    
    return summary


def monitor_alerts_realtime(alert_engine: AlertEngine, data_source_func):
    """Real-time alert monitoring (for testing/debugging)."""
    print("\n🚨 Real-time Alert Monitor (Press Ctrl+C to stop)")
    print("="*60)
    
    triggered_count = 0
    
    try:
        while True:
            import time
            
            # Get data from source function
            market_data = data_source_func()
            if not market_data:
                time.sleep(1)
                continue
            
            # Check for triggered alerts
            triggered = alert_engine.check_conditions(market_data)
            
            if triggered:
                triggered_count += len(triggered)
                print(f"\n⚠️  ALERT TRIGGERED at {datetime.now().strftime('%H:%M:%S')}")
                for alert in triggered:
                    print(f"   {alert.symbol}: {alert.type.value} - {alert.condition}")
                    print(f"   Value: {alert.current_value:.2f} (threshold: {alert.threshold:.2f})")
            
            time.sleep(1)  # Check every second
            
    except KeyboardInterrupt:
        print(f"\n✅ Monitoring stopped. Total alerts triggered: {triggered_count}")


def create_alert_dashboard():
    """Create a simple text-based alert dashboard."""
    print("""
🚨 ALERT SYSTEM DASHBOARD
========================

Available Commands:
1. show status    - Display current alert system status
2. show rules     - Display all alert rules
3. show history   - Display recent alert history  
4. show summary   - Display alert statistics
5. monitor        - Start real-time monitoring
6. exit           - Exit dashboard

Enter command: """, end="")


if __name__ == "__main__":
    # Demo of alert monitoring
    from src.alerts.alert_engine import AlertEngine
    from src.alerts.rules import PriceCrossRule, RSIExtremeRule
    
    # Create demo alert engine
    engine = AlertEngine()
    engine.add_rule(PriceCrossRule("DEMO", 100.0, "above"))
    engine.add_rule(RSIExtremeRule("DEMO"))
    
    # Display status
    display_alert_status(engine)
    display_alert_rules(engine)
    
    print("\n✅ Alert monitoring demo complete")