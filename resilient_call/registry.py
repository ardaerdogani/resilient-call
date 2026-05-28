"""
CircuitBreakerRegistry — a named, thread-safe store of CircuitBreaker instances.

Applications that manage multiple downstream dependencies can use the registry
to share breaker instances across modules without passing them explicitly.

The module-level :data:`registry` object is a ready-to-use singleton::

    from resilient_call.registry import registry

    cb = registry.get_or_create("payments-api")
"""

from __future__ import annotations

from threading import Lock
from typing import Dict, Iterator, Optional

from .circuit_breaker import CircuitBreaker, CircuitBreakerConfig


class CircuitBreakerRegistry:
    """Thread-safe registry mapping names to :class:`CircuitBreaker` instances.

    Example::

        from resilient_call.registry import registry

        # Create (or retrieve) a breaker with custom config
        cb = registry.get_or_create(
            "inventory-api",
            config=CircuitBreakerConfig(failure_threshold=3, timeout=30.0),
        )

        # Later, from any other module:
        cb = registry.get("inventory-api")
    """

    def __init__(self) -> None:
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = Lock()

    def get_or_create(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
    ) -> CircuitBreaker:
        """Return an existing breaker by *name*, or create and register one.

        If a breaker with *name* already exists the *config* argument is
        ignored — the existing instance is returned unchanged.

        Args:
            name: Unique identifier for the breaker.
            config: Configuration applied only when a new breaker is created.

        Returns:
            The :class:`CircuitBreaker` associated with *name*.
        """
        with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(name, config)
            return self._breakers[name]

    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Return the breaker registered under *name*, or ``None``.

        Args:
            name: Name to look up.

        Returns:
            :class:`CircuitBreaker` or ``None`` if not registered.
        """
        with self._lock:
            return self._breakers.get(name)

    def remove(self, name: str) -> bool:
        """Remove a breaker from the registry.

        Args:
            name: Name of the breaker to remove.

        Returns:
            ``True`` if the breaker was found and removed, ``False`` otherwise.
        """
        with self._lock:
            if name in self._breakers:
                del self._breakers[name]
                return True
            return False

    def reset_all(self) -> None:
        """Call :meth:`~CircuitBreaker.reset` on every registered breaker."""
        with self._lock:
            for cb in self._breakers.values():
                cb.reset()

    def clear(self) -> None:
        """Remove all breakers from the registry."""
        with self._lock:
            self._breakers.clear()

    def __iter__(self) -> Iterator[CircuitBreaker]:
        with self._lock:
            return iter(list(self._breakers.values()))

    def __len__(self) -> int:
        with self._lock:
            return len(self._breakers)

    def __repr__(self) -> str:
        with self._lock:
            names = list(self._breakers.keys())
        return f"CircuitBreakerRegistry(breakers={names!r})"


registry: CircuitBreakerRegistry = CircuitBreakerRegistry()
"""Module-level default registry.  Import and use directly in application code."""
