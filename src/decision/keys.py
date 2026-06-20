"""Provider API-key pool, selected by run mode.

Keys live in .env as a numbered pool (GROQ_API_KEY_1..N, GEMINI_API_KEY_1..N).
The two run modes use DISJOINT keys so a backtest can't starve a live session
(matches the notes' "1 live key / 3 backtest keys"):
  - live     → key 1   (PREFIX_API_KEY_1)
  - backtest → keys 2,3,4,...  (PREFIX_API_KEY_2 onward), cycled
Sensible fallbacks apply when the expected numbered keys aren't all present.
"""

import os
from typing import List, Dict


def _real(name: str) -> str:
    """Env value if it's a real (non-placeholder) key, else ''."""
    val = (os.getenv(name) or "").strip()
    return val if val and not val.startswith("your-") else ""


def _numbered(prefix: str) -> Dict[int, str]:
    """{index: key} for PREFIX_API_KEY_1..10 that are real."""
    out: Dict[int, str] = {}
    for i in range(1, 11):
        v = _real(f"{prefix}_API_KEY_{i}")
        if v:
            out[i] = v
    return out


def provider_keys(prefix: str, mode: str = "backtest") -> List[str]:
    """API keys for ``prefix`` selected by run ``mode``.

    live → ``[key 1]``; backtest/paper → ``[keys 2,3,4,...]`` (cycled). Falls back
    to the singular key or whatever numbered keys exist when the expected ones are
    absent, so a half-configured .env still works.
    """
    numbered = _numbered(prefix)
    singular = _real(f"{prefix}_API_KEY")

    if str(mode).lower() == "live":
        if 1 in numbered:
            return [numbered[1]]
        if singular:
            return [singular]
        return [numbered[min(numbered)]] if numbered else []

    # backtest / paper: keys 2 onward, cycled
    backtest = [numbered[i] for i in sorted(numbered) if i >= 2]
    if backtest:
        return backtest
    # fallbacks: any numbered key, then the singular
    allk = [numbered[i] for i in sorted(numbered)]
    if not allk and singular:
        allk = [singular]
    return allk
