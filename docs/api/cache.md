# cache

Memory cache implementation for market data.

## Class: `MemoryCache`

In-memory cache with TTL support.

### Methods

#### `__init__(self, ttl_seconds)`

Initialize cache with time-to-live.

#### `get(self, key)`

Get value from cache if not expired.

#### `set(self, key, value)`

Set value in cache.

#### `clear_expired(self)`

Remove all expired entries.

#### `clear(self)`

Clear all cache entries.

#### `size(self)`

Get current cache size.

#### `keys(self)`

Get all cache keys.

## Functions

### `__init__(self, ttl_seconds)`

Initialize cache with time-to-live.

### `get(self, key)`

Get value from cache if not expired.

### `set(self, key, value)`

Set value in cache.

### `clear_expired(self)`

Remove all expired entries.

### `clear(self)`

Clear all cache entries.

### `size(self)`

Get current cache size.

### `keys(self)`

Get all cache keys.

