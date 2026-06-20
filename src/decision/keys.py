"""Provider API-key pool.

Keys live in .env as a numbered pool (GROQ_API_KEY_1..N, GEMINI_API_KEY_1..N),
with the singular PREFIX_API_KEY accepted as a fallback. This module is the single
place that reads them. The coordinator builds its chain from the first available
key per provider today; full per-call cycling across the pool (1 key live / 3
backtest, rate-limit-proof) will extend this module in Phase 3.
"""

import os
from typing import List


def collect_provider_keys(prefix: str) -> List[str]:
    """Collect real API keys for ``prefix`` from the environment.

    Singular ``PREFIX_API_KEY`` first, then ``PREFIX_API_KEY_1..N`` ascending;
    de-duplicated, with blanks/placeholders dropped.
    """
    names = [f"{prefix}_API_KEY"] + [f"{prefix}_API_KEY_{i}" for i in range(1, 11)]
    keys: List[str] = []
    seen = set()
    for n in names:
        val = (os.getenv(n) or "").strip()
        if val and not val.startswith("your-") and val not in seen:
            seen.add(val)
            keys.append(val)
    return keys
