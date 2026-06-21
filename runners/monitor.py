#!/usr/bin/env python3
"""Live trading monitor — a terminal dashboard for a running backtest or live session.

Read-only. It consumes the STRUCTURED event stream the runners emit
(``data/logs/events.jsonl`` via ``platform.events.log_event``) plus the per-tick
account snapshot (``portfolio_state.json``) and the session pointer
(``current_session.json``). No log-prose parsing — every panel is driven by typed
events filtered to the CURRENT session, so reruns don't contaminate the view and a
reworded log line can't break the dashboard.

    python runners/monitor.py        # run in a 2nd terminal alongside a backtest/live run

Ctrl-C to quit.
"""

import os
import sys
import json
import time
from collections import deque
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.platform.session import read_session, is_alive
from src.platform.events import EVENTS_FILE
from src.platform.logger import LOGS_DIR

STATE_PATH = os.path.join(LOGS_DIR, 'portfolio_state.json')
SIGNAL_COLOR = {'BUY': 'bold green', 'SELL': 'bold red', 'HOLD': 'dim'}


def short_model(model: str) -> str:
    """groq:openai/gpt-oss-120b -> gpt-oss-120b (the part humans track)."""
    return model.split('/')[-1] if model else '?'


def hhmmss(iso_ts: str) -> str:
    """Pull HH:MM:SS out of an ISO/space timestamp for compact display."""
    return iso_ts[11:19] if iso_ts and len(iso_ts) >= 19 else (iso_ts or '')


class Tailer:
    """Follows one growing file, yielding newly-appended lines. Resets on rotation;
    starts near the end so the dashboard shows recent context at launch."""

    def __init__(self, path: str, tail_bytes: int = 32768):
        self.path = path
        self.offset = max(0, os.path.getsize(path) - tail_bytes) if os.path.exists(path) else 0

    def read_new(self):
        if not os.path.exists(self.path):
            return []
        size = os.path.getsize(self.path)
        if size < self.offset:
            self.offset = 0
        if size == self.offset:
            return []
        with open(self.path, 'r', errors='replace') as f:
            f.seek(self.offset)
            data = f.read()
            self.offset = f.tell()
        return data.splitlines()


class MonitorState:
    """Rolling view assembled from the structured event stream (one session)."""

    def __init__(self):
        self.ai_calls = deque(maxlen=8)
        self.decisions = deque(maxlen=12)
        self.alerts = deque(maxlen=12)
        self.fills = deque(maxlen=8)
        self.general_calls = 0
        self.special_calls = 0
        self.rate_limits = 0
        self.last_ratelimit = ''
        self.last_tick = ''
        self.last_analysis = ''

    def feed_event(self, rec: dict):
        typ = rec.get('type')
        t = hhmmss(rec.get('t', ''))

        if typ == 'tick':
            self.last_tick = rec.get('sim_time') or self.last_tick

        elif typ == 'ai_call':
            mode = 'ALERT' if rec.get('pass_type') == 'special' else 'GEN'
            self.ai_calls.append({'time': t, 'mode': mode,
                                  'model': rec.get('model', ''), 'latency': rec.get('latency', 0)})
            if mode == 'ALERT':
                self.special_calls += 1
            else:
                self.general_calls += 1

        elif typ == 'decision':
            src = 'ALERT' if rec.get('pass_type') == 'special' else 'GEN'
            self.decisions.append({'time': t, 'source': src, 'symbol': rec.get('symbol'),
                                   'signal': rec.get('signal'), 'conf': rec.get('confidence', 0)})

        elif typ == 'alert':
            self.alerts.append({'time': t, 'atype': rec.get('atype'), 'symbol': rec.get('symbol')})

        elif typ == 'fill':
            self.fills.append({'time': t, 'action': rec.get('action'), 'symbol': rec.get('symbol'),
                               'pnl_pct': rec.get('pnl_pct'), 'reason': rec.get('reason', '')})

        elif typ == 'analysis':
            self.last_analysis = (rec.get('text') or '')[:200]

        elif typ == 'rate_limit':
            self.rate_limits += 1
            self.last_ratelimit = rec.get('provider', '')


# ----------------------------- rendering -----------------------------

def render_account(state_doc) -> Panel:
    if not state_doc:
        return Panel(Text('waiting for portfolio_state.json…', style='dim'),
                     title='ACCOUNT', border_style='cyan')
    acc = state_doc.get('account', {})
    ret = acc.get('total_return', 0.0)
    t = Table.grid(padding=(0, 1))
    t.add_column(justify='right', style='dim')
    t.add_column()
    t.add_row('equity', f"₹{acc.get('current_capital', 0):,.0f}")
    t.add_row('cash', f"₹{acc.get('available_capital', 0):,.0f}")
    t.add_row('return', Text(f"{ret:+.2f}%", style='bold green' if ret >= 0 else 'bold red'))
    t.add_row('drawdown', f"{acc.get('max_drawdown', 0):.2f}%")
    t.add_row('win rate', f"{acc.get('win_rate', 0):.0f}%  ({acc.get('closed_trades', 0)} closed)")
    t.add_row('open pos', str(acc.get('open_positions', 0)))
    t.add_row('charges', f"₹{acc.get('total_commission', 0):,.1f}")
    return Panel(t, title='ACCOUNT', border_style='cyan')


def render_positions(state_doc) -> Panel:
    positions = (state_doc or {}).get('positions', {})
    t = Table(expand=True, box=None, pad_edge=False)
    for c, j in (('Sym', 'left'), ('Qty', 'right'), ('Entry', 'right'), ('Last', 'right'), ('P&L%', 'right')):
        t.add_column(c, justify=j, style='bold' if c == 'Sym' else None)
    if not positions:
        t.add_row('—', '', '', '', '')
    for sym, p in positions.items():
        pnl = p.get('pnl_percent') or 0.0
        t.add_row(sym, str(p.get('quantity', '')), f"{p.get('entry_price', 0):.1f}",
                  f"{p.get('current_price', 0):.1f}",
                  Text(f"{pnl:+.2f}", style='green' if pnl >= 0 else 'red'))
    return Panel(t, title=f'POSITIONS ({len(positions)})', border_style='cyan')


def render_ai_calls(state: MonitorState) -> Panel:
    t = Table(expand=True, box=None, pad_edge=False)
    t.add_column('Time', style='dim'); t.add_column('Type'); t.add_column('Model'); t.add_column('s', justify='right')
    for c in reversed(state.ai_calls):
        t.add_row(c['time'], Text(c['mode'], style='yellow' if c['mode'] == 'ALERT' else 'cyan'),
                  short_model(c['model']), f"{c['latency']:.1f}")
    return Panel(t, title='AI CALLS', border_style='magenta')


def render_decisions(state: MonitorState) -> Panel:
    t = Table(expand=True, box=None, pad_edge=False)
    t.add_column('Time', style='dim'); t.add_column('Src'); t.add_column('Sym', style='bold')
    t.add_column('Signal'); t.add_column('Conf', justify='right')
    for d in reversed(state.decisions):
        t.add_row(d['time'], Text(d['source'], style='yellow' if d['source'] == 'ALERT' else 'dim'),
                  d['symbol'] or '?', Text(d['signal'] or '?', style=SIGNAL_COLOR.get(d['signal'], '')),
                  f"{d['conf']:.2f}")
    return Panel(t, title='DECISIONS', border_style='green')


def render_alerts(state: MonitorState) -> Panel:
    t = Table(expand=True, box=None, pad_edge=False)
    t.add_column('Time', style='dim'); t.add_column('Type', style='yellow'); t.add_column('Sym', style='bold')
    for a in reversed(state.alerts):
        t.add_row(a['time'], a['atype'] or '?', a['symbol'] or '?')
    return Panel(t, title='ALERTS', border_style='yellow')


def render_fills(state: MonitorState) -> Panel:
    t = Table(expand=True, box=None, pad_edge=False)
    t.add_column('Time', style='dim'); t.add_column('Act'); t.add_column('Sym', style='bold'); t.add_column('P&L%', justify='right')
    for f in reversed(state.fills):
        label = (f['action'] or '?') + (f"·{f['reason']}" if f.get('reason') and f['reason'] != 'SIGNAL' else '')
        pnl = f.get('pnl_pct')
        pnl_txt = Text(f"{float(pnl):+.2f}", style='green' if float(pnl) >= 0 else 'red') if pnl is not None else Text('')
        t.add_row(f['time'], Text(label, style={'BUY': 'green', 'SELL': 'red'}.get(f['action'], 'magenta')),
                  f['symbol'] or '?', pnl_txt)
    return Panel(t, title='FILLS', border_style='red')


def _state_age(snap_ts: str):
    try:
        return (datetime.now() - datetime.fromisoformat(snap_ts)).total_seconds()
    except Exception:
        return None


def render_header(state: MonitorState, state_doc, session) -> Panel:
    snap_ts = (state_doc or {}).get('timestamp', '—')
    age = _state_age(snap_ts)
    if not session:
        status, sid, border = Text('no registered session', style='bold yellow'), '—', 'yellow'
    else:
        sid = session.get('session_id', '?')
        alive = is_alive(session.get('pid'))
        if alive and (age is None or age < 120):
            status, border = Text('● LIVE', style='bold green'), 'green'
        elif alive:
            status, border = Text(f'● LIVE (idle {age:.0f}s)', style='bold yellow'), 'yellow'
        else:
            status, border = Text('○ ENDED', style='bold red'), 'red'
    line1 = Text.assemble(('TRADING MONITOR  ', 'bold white'), status,
                          ('   ', ''), (sid, 'cyan'),
                          ('  ', ''), (f"[{session['mode']}]" if session else '', 'magenta'))
    line2 = Text.assemble(('sim-tick ', 'dim'), (state.last_tick or '—', 'bold cyan'),
                          ('   state @ ', 'dim'), (snap_ts, 'green'),
                          (f"  ({age:.0f}s ago)" if age is not None else '', 'dim'))
    return Panel(Group(line1, line2), border_style=border)


def render_footer(state: MonitorState) -> Panel:
    rl = f"{state.rate_limits}" + (f" ({short_model(state.last_ratelimit)})" if state.last_ratelimit else '')
    counters = Text.assemble(
        ('general calls ', 'dim'), (str(state.general_calls), 'bold cyan'),
        ('   alert calls ', 'dim'), (str(state.special_calls), 'bold yellow'),
        ('   rate-limits ', 'dim'), (rl, 'bold red'),
        ('   fills ', 'dim'), (str(len(state.fills)), 'bold'),
    )
    return Panel(Group(counters, Text(state.last_analysis or 'no market analysis yet', style='italic dim')),
                 title='ACTIVITY', border_style='blue')


def build_layout(state: MonitorState, state_doc, session) -> Layout:
    root = Layout()
    root.split_column(
        Layout(render_header(state, state_doc, session), name='header', size=4),
        Layout(name='body'),
        Layout(render_footer(state), name='footer', size=4),
    )
    root['body'].split_row(Layout(name='left'), Layout(name='mid'), Layout(name='right'))
    root['body']['left'].split_column(
        Layout(render_account(state_doc), name='acc', size=11),
        Layout(render_positions(state_doc), name='pos'))
    root['body']['mid'].split_column(
        Layout(render_ai_calls(state), name='ai'),
        Layout(render_decisions(state), name='dec'))
    root['body']['right'].split_column(
        Layout(render_alerts(state), name='alr'),
        Layout(render_fills(state), name='fill'))
    return root


def read_state_doc():
    try:
        with open(STATE_PATH) as f:
            return json.load(f)
    except Exception:
        return None


def main():
    console = Console()
    tailer = Tailer(EVENTS_FILE)
    state = MonitorState()

    with Live(console=console, screen=True, refresh_per_second=4) as live:
        try:
            while True:
                session = read_session()
                sid = session.get('session_id') if session else None
                for line in tailer.read_new():
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    # Only the current run's events (events.jsonl is append-only across runs).
                    if sid and rec.get('session') not in (sid, None):
                        continue
                    state.feed_event(rec)
                live.update(build_layout(state, read_state_doc(), session))
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
    console.print('[dim]monitor stopped[/dim]')


if __name__ == '__main__':
    main()
