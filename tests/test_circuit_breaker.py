"""Tests for CircuitBreaker and CircuitBreakerConfig."""

import time
import pytest
from unittest.mock import MagicMock

from resilient_call.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitBreakerState
from resilient_call.exceptions import CircuitBreakerError


def make_cb(failure_threshold=3, success_threshold=2, timeout=60.0):
    config = CircuitBreakerConfig(
        failure_threshold=failure_threshold,
        success_threshold=success_threshold,
        timeout=timeout,
    )
    return CircuitBreaker("test", config)


def trip_and_advance(cb: CircuitBreaker) -> None:
    """Trip the breaker then backdate _opened_at so the timeout has already elapsed."""
    with pytest.raises(IOError):
        cb.call(MagicMock(side_effect=IOError))
    assert cb.state == CircuitBreakerState.OPEN
    cb._opened_at = time.monotonic() - cb.config.timeout - 1.0


class TestClosedState:
    def test_starts_closed(self):
        cb = make_cb()
        assert cb.state == CircuitBreakerState.CLOSED

    def test_success_keeps_closed(self):
        cb = make_cb()
        cb.call(lambda: 42)
        assert cb.state == CircuitBreakerState.CLOSED

    def test_success_resets_failure_count(self):
        cb = make_cb(failure_threshold=3)
        fail = MagicMock(side_effect=IOError)
        for _ in range(2):
            with pytest.raises(IOError):
                cb.call(fail)
        assert cb.failure_count == 2
        cb.call(lambda: None)
        assert cb.failure_count == 0

    def test_consecutive_failures_trip_open(self):
        cb = make_cb(failure_threshold=3)
        fail = MagicMock(side_effect=IOError)
        for _ in range(3):
            with pytest.raises(IOError):
                cb.call(fail)
        assert cb.state == CircuitBreakerState.OPEN

    def test_non_expected_exception_does_not_count(self):
        config = CircuitBreakerConfig(
            failure_threshold=2,
            expected_exceptions=(IOError,),
        )
        cb = CircuitBreaker("test", config)
        with pytest.raises(ValueError):
            cb.call(MagicMock(side_effect=ValueError("unexpected")))
        assert cb.failure_count == 0
        assert cb.state == CircuitBreakerState.CLOSED


class TestOpenState:
    def test_open_blocks_calls(self):
        cb = make_cb(failure_threshold=1)
        with pytest.raises(IOError):
            cb.call(MagicMock(side_effect=IOError))
        assert cb.state == CircuitBreakerState.OPEN
        with pytest.raises(CircuitBreakerError):
            cb.call(lambda: 99)

    def test_circuit_breaker_error_carries_name(self):
        config = CircuitBreakerConfig(failure_threshold=1)
        cb = CircuitBreaker("my-service", config)
        with pytest.raises(IOError):
            cb.call(MagicMock(side_effect=IOError))
        with pytest.raises(CircuitBreakerError) as exc_info:
            cb.call(lambda: None)
        assert exc_info.value.name == "my-service"

    def test_transitions_to_half_open_after_timeout(self):
        cb = make_cb(failure_threshold=1, timeout=1.0)
        with pytest.raises(IOError):
            cb.call(MagicMock(side_effect=IOError))
        assert cb.state == CircuitBreakerState.OPEN
        # Simulate timeout elapsed by backdating _opened_at
        cb._opened_at = time.monotonic() - 2.0
        assert cb.state == CircuitBreakerState.HALF_OPEN


class TestHalfOpenState:
    def test_success_in_half_open_closes(self):
        cb = make_cb(failure_threshold=1, success_threshold=2, timeout=1.0)
        trip_and_advance(cb)
        assert cb.state == CircuitBreakerState.HALF_OPEN
        cb.call(lambda: None)
        cb.call(lambda: None)
        assert cb.state == CircuitBreakerState.CLOSED

    def test_failure_in_half_open_reopens(self):
        cb = make_cb(failure_threshold=1, success_threshold=2, timeout=1.0)
        trip_and_advance(cb)
        assert cb.state == CircuitBreakerState.HALF_OPEN
        with pytest.raises(IOError):
            cb.call(MagicMock(side_effect=IOError))
        assert cb.state == CircuitBreakerState.OPEN


class TestReset:
    def test_manual_reset_closes_open_breaker(self):
        cb = make_cb(failure_threshold=1)
        with pytest.raises(IOError):
            cb.call(MagicMock(side_effect=IOError))
        assert cb.state == CircuitBreakerState.OPEN
        cb.reset()
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0


class TestStateChangeCallback:
    def test_callback_invoked_on_open(self):
        events = []
        config = CircuitBreakerConfig(
            failure_threshold=1,
            on_state_change=lambda name, old, new: events.append((old, new)),
        )
        cb = CircuitBreaker("cb", config)
        with pytest.raises(IOError):
            cb.call(MagicMock(side_effect=IOError))
        assert (CircuitBreakerState.CLOSED, CircuitBreakerState.OPEN) in events
