"""Structured domain-event log — the analysis/monitor source of truth.

Every decision / AI-call / alert / fill / tick is appended as one JSON line to
``data/logs/events.jsonl``, stamped with wall-clock time and the active
``session_id``. This is deliberately separate from the human-readable text logs:
those stay for debugging; THIS is the typed, machine-read stream the monitor and
any analysis consume — so they never have to regex prose, and per-run filtering is
just ``where session == …``.

Schema is by convention (the ``type`` field + that type's fields). Common envelope:
``{t, type, session, **fields}``. Keep field names stable — the monitor depends on
them (it's a contract now, not a log message).
"""

import os
import json
import threading
from datetime import datetime
from typing import Optional

from src.platform.logger import LOGS_DIR

EVENTS_FILE = os.path.join(LOGS_DIR, 'events.jsonl')

_session_id: Optional[str] = None
_lock = threading.Lock()


def set_session(session_id: Optional[str]):
    """Stamp subsequent events with this session id (called by register_session)."""
    global _session_id
    _session_id = session_id


def log_event(event_type: str, **fields):
    """Append one structured event. Never raises — a logging miss must not abort
    a trading tick."""
    record = {'t': datetime.now().isoformat(timespec='seconds'),
              'type': event_type, 'session': _session_id, **fields}
    try:
        with _lock, open(EVENTS_FILE, 'a') as f:
            f.write(json.dumps(record, default=str) + '\n')
    except Exception:
        pass
