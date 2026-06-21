#!/usr/bin/env python3
"""Live runner — PAPER fills on LIVE Zerodha data.

The live counterpart to runners/backtest.py. Same shared core (Feed →
TradingPipeline → risk → PaperTrader, plus AlertManager), but driven by a
WALL-CLOCK schedule instead of replaying historical timestamps:

  - GENERAL pass every ``--general-min`` minutes (all symbols → Flash) — registers
    the AI's alert_conditions.
  - ALERT checks every ``--alert-min`` minutes between general passes; a triggered
    symbol gets a fast single-symbol SPECIAL pass (gpt-oss) → risk → paper fill.

This matches the notes' "≈90-min cycles with ~5-min monitoring between". Fills are
PAPER (no real orders — ZerodhaAPI is data-only). Requires a fresh daily Zerodha
token (scripts/generate_zerodha_token.py) and runs during market hours.

    python runners/live.py                       # default cadence, configured symbols
    python runners/live.py --general-min 90 --alert-min 5 --symbols RELIANCE TCS
    python runners/live.py --ignore-market-hours # for off-hours smoke testing
"""

import os
import sys
import time
import argparse
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.platform.config import SYMBOLS, INITIAL_CAPITAL, is_market_hours
from src.platform.logger import setup_logger
from src.marketdata.feed import LiveSource, Feed
from src.marketdata.collector import DataCollector
from src.marketdata.backfill import ensure_recent_history
from src.platform.events import log_event
from src.decision.engine import AIBrain
from src.risk.manager import SimpleRiskManager
from src.execution.executor import PaperTrader
from src.alerts.manager import AlertManager
from src.pipeline import TradingPipeline

logger = setup_logger(__name__, 'live.log')


class LiveTrader:
    """Real-time paper-trading loop over live Zerodha data."""

    def __init__(self, symbols, general_min=90, alert_min=5, ignore_market_hours=False,
                 backfill_days=300):
        self.symbols = symbols
        self.general_min = general_min
        self.alert_min = alert_min
        self.ignore_market_hours = ignore_market_hours
        self.backfill_days = backfill_days

        self.source = LiveSource()
        self.feed = Feed(self.source)
        self.collector = DataCollector()  # persists live bars so DB history grows
        self.brain = AIBrain(mode='live')  # key 1 (reserved for live)
        self.risk = SimpleRiskManager()
        self.trader = PaperTrader(initial_capital=INITIAL_CAPITAL)
        self.pipeline = TradingPipeline(self.brain, self.risk, self.trader)
        self.alerts = AlertManager(symbols)
        logger.info(f"LiveTrader ready: {len(symbols)} symbols, general every {general_min}m, "
                    f"alerts every {alert_min}m (PAPER fills on live data)")

    # ----- one tick: refresh live bars, build per-symbol data -----------------------

    def _gather(self):
        """Fetch + persist live bars, then build portfolio_data / indicators / prices /
        snapshots for the symbols that have enough history."""
        portfolio_data, portfolio_indicators, current_prices, snapshots = {}, {}, {}, {}
        for symbol in self.symbols:
            # One live fetch per symbol: collect_and_store fetches, validates and
            # persists the bar (growing DB history) AND returns it, so we reuse it as
            # the current bar instead of issuing a second live quote via feed.current.
            try:
                current = self.collector.collect_and_store(symbol)
            except Exception as e:
                logger.debug(f"collect_and_store failed for {symbol}: {e}")
                current = None
            if current is None:
                # Collector skipped this bar (e.g. the zero-volume index ^NSEI, which
                # the validator rejects, or a transient miss). Fall back to a direct
                # live bar so regime inputs still flow; tradeable stocks took the
                # single-fetch path above.
                current = self.feed.current(symbol)
            if not current:
                continue
            hist = self.feed.history(symbol)
            if len(hist) < 20:
                continue
            indicators = self.feed.indicators(symbol)
            if not indicators:
                continue
            hist = hist.copy()
            hist['symbol'] = symbol
            portfolio_data[symbol] = hist
            portfolio_indicators[symbol] = indicators
            current_prices[symbol] = current.close
            snapshots[symbol] = {'close': current.close, 'volume': current.volume, 'indicators': indicators}
        # Mechanical stop/target floor on live prices (the backstop beneath the
        # AI/alert layer), then snapshot account state for the monitor. A close
        # changes the book, so refresh management alert levels for the closed name.
        if current_prices:
            closed = self.pipeline.manage_positions(current_prices)
            for ex in closed:
                logger.warning(f"Mechanical {ex.get('exit_reason')} for {ex['symbol']} @ "
                               f"₹{ex.get('price', 0):.2f} (P&L {ex.get('pnl_percent', 0):+.2f}%)")
            if closed:
                self.alerts.refresh(self.trader.get_positions())
            self.trader.book.write_state()
        return portfolio_data, portfolio_indicators, current_prices, snapshots

    def _general_pass(self):
        pdata, pind, prices, _ = self._gather()
        if not pdata:
            logger.warning("General pass: no symbols with sufficient data")
            return
        log_event('tick', sim_time=datetime.now().isoformat(timespec='seconds'),
                  symbols=len(pdata), pass_type='general')
        positions = self.trader.get_positions()
        context = {
            'strategy': 'swing',
            'timestamp': datetime.now().isoformat(timespec='seconds'),
            'current_positions': [s for s, p in positions.items() if p.get('quantity', 0) > 0],
            'positions': positions,
            'account_info': self.trader.get_account_info(),
        }
        result = self.pipeline.run_decisions(pdata, pind, prices, context)
        self.alerts.update_from_general(result['decisions'], positions)
        logger.info(f"General pass: {len(result['decisions'])} decisions, "
                    f"{len(result['executed'])} executed. {result['market_analysis'][:120]}")

    def _alert_pass(self):
        pdata, pind, prices, snaps = self._gather()
        if not pdata:
            return
        log_event('tick', sim_time=datetime.now().isoformat(timespec='seconds'),
                  symbols=len(pdata), pass_type='alert')
        triggered = self.alerts.evaluate(snaps)
        if not triggered:
            logger.info("Alert check: no triggers")
            return
        logger.info(f"Alert check: triggered {list(triggered)}")
        for symbol in triggered:
            if symbol not in pdata:
                continue
            try:
                out = self.pipeline.run_special(symbol, pdata[symbol], pind[symbol], prices[symbol],
                                                alert_context=triggered[symbol])
                d = out['decision']
                ex = out.get('executed')
                logger.info(f"Special pass {symbol}: {d.get('signal')} (conf {d.get('confidence')})"
                            + (f" -> {ex.get('status')}" if ex else ""))
                if ex and ex.get('status') == 'EXECUTED':
                    # Book changed → re-derive this symbol's management alert levels.
                    self.alerts.refresh(self.trader.get_positions())
            except Exception as e:
                logger.error(f"Special pass error for {symbol}: {e}")

    # ----- the wall-clock loop ------------------------------------------------------

    def run(self):
        logger.info("=" * 60)
        logger.info("LIVE PAPER TRADING — Ctrl-C to stop")
        logger.info("=" * 60)
        if not self.source.is_available():
            logger.error("Zerodha not authenticated — refresh the token "
                         "(scripts/generate_zerodha_token.py) and retry. Aborting.")
            return

        # Register this run so the monitor can identify + liveness-check it.
        from src.platform.session import register_session
        register_session('live', symbols=self.symbols, capital=INITIAL_CAPITAL,
                         general_min=self.general_min, alert_min=self.alert_min)

        # Fill any gap in stored history so indicators warm up on the first tick.
        # Reuse LiveSource's authenticated session and the collector's DB connection.
        if self.backfill_days > 0:
            logger.info(f"--- BACKFILL: ensuring ~{self.backfill_days}d of history ---")
            ensure_recent_history(self.symbols, lookback_days=self.backfill_days,
                                  zerodha=self.source.api, db=self.collector.db)

        last_general = 0.0
        try:
            while True:
                now = time.time()
                if not self.ignore_market_hours and not is_market_hours():
                    logger.info("Outside market hours — sleeping 5 min")
                    time.sleep(300)
                    continue

                if now - last_general >= self.general_min * 60:
                    logger.info("--- GENERAL pass ---")
                    self._general_pass()
                    last_general = now
                else:
                    logger.info("--- ALERT check ---")
                    self._alert_pass()

                time.sleep(self.alert_min * 60)
        except KeyboardInterrupt:
            logger.info("\nStopped by user. Final account:")
            logger.info(self.trader.get_account_info())
        finally:
            self.source.close()


def build_arg_parser():
    p = argparse.ArgumentParser(description="Live paper trading on live Zerodha data")
    p.add_argument('--symbols', nargs='+', help='Symbols (default: configured)')
    p.add_argument('--general-min', type=int, default=90, help='Minutes between general passes (default 90)')
    p.add_argument('--alert-min', type=int, default=5, help='Minutes between alert checks (default 5)')
    p.add_argument('--backfill-days', type=int, default=300,
                   help='Days of history to ensure in the DB before starting '
                        '(~300 ≈ 200 trading bars, enough to warm SMA-200; 0 to skip)')
    p.add_argument('--ignore-market-hours', action='store_true', help='Run even outside market hours (testing)')
    return p


def main():
    args = build_arg_parser().parse_args()
    LiveTrader(
        symbols=args.symbols or SYMBOLS,
        general_min=args.general_min,
        alert_min=args.alert_min,
        ignore_market_hours=args.ignore_market_hours,
        backfill_days=args.backfill_days,
    ).run()


if __name__ == "__main__":
    main()
