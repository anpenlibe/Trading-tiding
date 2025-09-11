# retry

Retry logic utilities.

## Class: `CircuitBreaker`

Circuit breaker pattern implementation.

### Methods

#### `__init__(self, failure_threshold, recovery_timeout)`

Initialize circuit breaker.

Args:
    failure_threshold: Number of failures before opening circuit
    recovery_timeout: Time in seconds before attempting to close circuit

#### `call(self, func)`

Execute function with circuit breaker protection.

## Functions

### `retry_with_backoff(max_retries, initial_delay, max_delay, exponential_base, exceptions, on_retry)`

Decorator for retrying functions with exponential backoff.

Args:
    max_retries: Maximum number of retry attempts
    initial_delay: Initial delay between retries in seconds
    max_delay: Maximum delay between retries
    exponential_base: Base for exponential backoff
    exceptions: Tuple of exceptions to catch and retry
    on_retry: Optional callback function called on each retry

### `decorator(func)`

### `__init__(self, failure_threshold, recovery_timeout)`

Initialize circuit breaker.

Args:
    failure_threshold: Number of failures before opening circuit
    recovery_timeout: Time in seconds before attempting to close circuit

### `call(self, func)`

Execute function with circuit breaker protection.

### `wrapper()`

