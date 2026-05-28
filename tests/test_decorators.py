"""Tests for @retry and @circuit_breaker decorators."""

import pytest
from unittest.mock import MagicMock

from resilient_call.decorators import circuit_breaker, retry
from resilient_call.exceptions import CircuitBreakerError, RetryExhaustedError
from resilient_call.registry import registry


@pytest.fixture(autouse=True)
def clear_registry():
    """Ensure each test starts with a clean circuit breaker registry."""
    registry.clear()
    yield
    registry.clear()


class TestRetryDecorator:
    def test_decorator_retries_on_failure(self):
        calls = []

        @retry(max_attempts=3, delay=0.0)
        def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise IOError("transient")
            return "ok"

        assert flaky() == "ok"
        assert len(calls) == 3

    def test_decorator_raises_when_exhausted(self):
        @retry(max_attempts=2, delay=0.0)
        def always_fails():
            raise IOError("always")

        with pytest.raises(RetryExhaustedError):
            always_fails()

    def test_retry_policy_attached_to_wrapper(self):
        @retry(max_attempts=4)
        def func():
            pass

        assert func.__retry_policy__.max_attempts == 4

    def test_decorator_preserves_function_name(self):
        @retry()
        def my_function():
            pass

        assert my_function.__name__ == "my_function"


class TestCircuitBreakerDecorator:
    def test_decorator_passes_through_on_success(self):
        @circuit_breaker("svc-ok", failure_threshold=3)
        def ok():
            return "result"

        assert ok() == "result"

    def test_decorator_trips_after_threshold(self):
        @circuit_breaker("svc-trip", failure_threshold=2)
        def boom():
            raise IOError("down")

        for _ in range(2):
            with pytest.raises(IOError):
                boom()

        with pytest.raises(CircuitBreakerError):
            boom()

    def test_fallback_invoked_on_all_failures(self):
        """Fallback is called for any exception, not only when circuit is open."""
        @circuit_breaker("svc-fallback", failure_threshold=5, fallback=lambda exc: "safe")
        def risky():
            raise IOError("gone")

        # Fallback returns "safe" regardless of circuit state
        assert risky() == "safe"
        assert risky() == "safe"

    def test_fallback_used_when_circuit_open(self):
        """After the circuit trips, fallback still returns a safe value."""
        @circuit_breaker("svc-open", failure_threshold=1, fallback=lambda exc: "safe")
        def risky():
            raise IOError("gone")

        # First call: fails and trips the circuit, fallback returns "safe"
        assert risky() == "safe"
        # Second call: circuit is OPEN, fallback returns "safe"
        assert risky() == "safe"

    def test_breaker_registered_in_registry(self):
        @circuit_breaker("svc-registry", failure_threshold=5)
        def service():
            return 1

        service()
        assert registry.get("svc-registry") is not None

    def test_decorator_preserves_function_name(self):
        @circuit_breaker("svc-name")
        def my_service():
            pass

        assert my_service.__name__ == "my_service"
