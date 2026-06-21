"""Session registry — links the monitor to a specific running session.

A runner calls ``register_session(...)`` at startup, which writes a single pointer
file (``data/logs/current_session.json``) describing the active run: a unique
session id, the mode, the OS pid, start time, and any metadata (symbols, capital,
cadence). The monitor reads this to show WHICH run it is following and — via the
pid — whether that run is still alive or has ended, so a stale ``portfolio_state``
from a finished run isn't shown as if it were live.

Deliberately lightweight: logs still share fixed paths (one active run at a time),
but the session pointer + pid liveness give an explicit, checkable identity.
"""

import os
import json
from datetime import datetime
from typing import Optional, Dict, Any

from src.platform.logger import LOGS_DIR

SESSION_FILE = os.path.join(LOGS_DIR, 'current_session.json')


def register_session(mode: str, **meta: Any) -> Dict[str, Any]:
    """Record the active session and return its record.

    ``mode`` is 'backtest' or 'live'; ``meta`` is free-form (symbols, capital, …).
    Overwrites any previous pointer — the newest run owns the shared log paths.
    """
    pid = os.getpid()
    session = {
        'session_id': f"{mode}-{datetime.now():%Y%m%d-%H%M%S}-{pid}",
        'mode': mode,
        'pid': pid,
        'started_at': datetime.now().isoformat(timespec='seconds'),
        **meta,
    }
    try:
        with open(SESSION_FILE, 'w') as f:
            json.dump(session, f, default=str)
    except Exception:
        pass  # a missing session pointer must never abort a run

    # Stamp every structured event with this run's id.
    from src.platform.events import set_session
    set_session(session['session_id'])
    return session


def read_session() -> Optional[Dict[str, Any]]:
    """The current session pointer, or None if no run has registered one."""
    try:
        with open(SESSION_FILE) as f:
            return json.load(f)
    except Exception:
        return None


def is_alive(pid: Optional[int]) -> bool:
    """True if a process with ``pid`` currently exists (signal-0 probe)."""
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError, TypeError):
        return False
