"""Tests for RetryPolicy and BackoffStrategy."""

import pytest
from unittest.mock import MagicMock, call

from resilient_call.retry import BackoffStrategy, RetryPolicy
from resilient_call.exceptions import RetryExhaustedError


class TestRetryPolicy:
    def test_success_on_first_attempt(self):
        policy = RetryPolicy(max_attempts=3)
        func = MagicMock(return_value=42)
        assert policy.execute(func) == 42
        func.assert_called_once()

    def test_retries_on_failure_then_succeeds(self):
        policy = RetryPolicy(max_attempts=3, delay=0.0)
        func = MagicMock(side_effect=[IOError, IOError, "ok"])
        assert policy.execute(func) == "ok"
        assert func.call_count == 3

    def test_raises_retry_exhausted_when_all_fail(self):
        policy = RetryPolicy(max_attempts=3, delay=0.0)
        func = MagicMock(side_effect=IOError("boom"))
        with pytest.raises(RetryExhaustedError) as exc_info:
            policy.execute(func)
        assert exc_info.value.attempts == 3
        assert isinstance(exc_info.value.last_exception, IOError)

    def test_non_retryable_exception_is_reraised_immediately(self):
        policy = RetryPolicy(
            max_attempts=5,
            delay=0.0,
            retryable_exceptions=(IOError,),
        )
        func = MagicMock(side_effect=ValueError("not retryable"))
        with pytest.raises(ValueError):
            policy.execute(func)
        func.assert_called_once()

    def test_on_retry_callback_invoked(self):
        events = []
        policy = RetryPolicy(
            max_attempts=3,
            delay=0.0,
            on_retry=lambda attempt, delay, exc: events.append(attempt),
        )
        func = MagicMock(side_effect=[IOError, IOError, "ok"])
        policy.execute(func)
        assert events == [1, 2]

    def test_max_attempts_one_means_no_retry(self):
        policy = RetryPolicy(max_attempts=1, delay=0.0)
        func = MagicMock(side_effect=IOError)
        with pytest.raises(RetryExhaustedError):
            policy.execute(func)
        func.assert_called_once()


class TestBackoffDelay:
    def test_fixed_strategy_constant_delay(self):
        policy = RetryPolicy(delay=2.0, backoff=BackoffStrategy.FIXED)
        assert policy.get_delay(1) == 2.0
        assert policy.get_delay(5) == 2.0

    def test_exponential_strategy_doubles(self):
        policy = RetryPolicy(delay=1.0, backoff=BackoffStrategy.EXPONENTIAL, max_delay=100.0)
        assert policy.get_delay(1) == 1.0
        assert policy.get_delay(2) == 2.0
        assert policy.get_delay(3) == 4.0
        assert policy.get_delay(4) == 8.0

    def test_max_delay_caps_exponential(self):
        policy = RetryPolicy(delay=1.0, backoff=BackoffStrategy.EXPONENTIAL, max_delay=5.0)
        assert policy.get_delay(10) == 5.0

    def test_jitter_within_bounds(self):
        policy = RetryPolicy(delay=1.0, backoff=BackoffStrategy.JITTER, max_delay=100.0)
        for _ in range(50):
            d = policy.get_delay(3)
            assert 0.0 <= d <= 4.0


class TestAsyncRetry:
    @pytest.mark.asyncio
    async def test_async_success(self):
        policy = RetryPolicy(max_attempts=3, delay=0.0)

        async def afunc():
            return "async_ok"

        assert await policy.execute_async(afunc) == "async_ok"

    @pytest.mark.asyncio
    async def test_async_retry_then_success(self):
        policy = RetryPolicy(max_attempts=3, delay=0.0)
        calls = []

        async def afunc():
            calls.append(1)
            if len(calls) < 3:
                raise IOError("transient")
            return "done"

        assert await policy.execute_async(afunc) == "done"
        assert len(calls) == 3
