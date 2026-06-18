"""Regression tests for the MemoryCache TTL cache.

Pins set/get/size/clear, lazy eviction on get after expiry, and that the dead
methods removed during cleanup (clear_expired, keys — zero references) stay gone.
A controllable clock avoids real sleeps.
"""

from src.data.cache import MemoryCache


def test_set_get_size_clear():
    c = MemoryCache(ttl_seconds=100)
    assert c.size() == 0
    c.set("a", 1)
    c.set("b", 2)
    assert c.get("a") == 1
    assert c.size() == 2
    c.clear()
    assert c.size() == 0
    assert c.get("a") is None


def test_get_missing_key_returns_none():
    assert MemoryCache(ttl_seconds=100).get("nope") is None


def test_entry_expires_and_is_evicted_on_get(monkeypatch):
    clock = {"t": 1000.0}
    monkeypatch.setattr("src.data.cache.time.time", lambda: clock["t"])
    c = MemoryCache(ttl_seconds=10)
    c.set("k", "v")
    assert c.get("k") == "v"      # still fresh
    clock["t"] += 11             # advance past the TTL
    assert c.get("k") is None     # expired
    assert c.size() == 0          # lazily evicted on the expired get


def test_removed_dead_methods_stay_removed():
    c = MemoryCache()
    assert not hasattr(c, "clear_expired")
    assert not hasattr(c, "keys")
