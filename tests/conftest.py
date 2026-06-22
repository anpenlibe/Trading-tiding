"""Shared test setup.

Two things every test in this suite needs before importing project modules:

1. A non-placeholder AI key. ``src/platform/config.py`` validates at IMPORT time
   that at least one Groq/Gemini key exists (it ``raise``s otherwise), and almost
   every module imports config transitively. Setting a dummy key here — before any
   test module is imported — lets the pure logic under test import cleanly without a
   real ``.env``. The value is never used to call an API; these tests make no
   network calls.
2. The repo root on ``sys.path`` so ``import src...`` resolves when pytest is run
   from anywhere.
"""

import os
import sys
import pathlib

os.environ.setdefault("GROQ_API_KEY", "test-key-not-placeholder")

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
