"""Per-provider rate limiting with circuit breaker pattern."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock

from ai_bos.logging_config import log


@dataclass
class RateLimit:
    requests_per_second: float
    burst: int


@dataclass
class CircuitBreaker:
    failure_threshold: int = 5
    recovery_timeout: float = 300.0   # 5 minutes
    failures: int = 0
    last_failure_time: float = 0.0
    is_open: bool = False
    _lock: Lock = field(default_factory=Lock)

    def record_failure(self) -> None:
        with self._lock:
            self.failures += 1
            self.last_failure_time = time.time()
            if self.failures >= self.failure_threshold:
                self.is_open = True
                log.warning("circuit_breaker.opened", failures=self.failures)

    def record_success(self) -> None:
        with self._lock:
            self.failures = 0
            self.is_open = False

    def can_proceed(self) -> bool:
        with self._lock:
            if not self.is_open:
                return True
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.is_open = False
                self.failures = 0
                log.info("circuit_breaker.recovered")
                return True
            return False


RATE_LIMITS: dict[str, RateLimit] = {
    "sendgrid": RateLimit(requests_per_second=100, burst=500),
    "twilio_sms": RateLimit(requests_per_second=10, burst=50),
    "twilio_voice": RateLimit(requests_per_second=5, burst=20),
    "stripe": RateLimit(requests_per_second=25, burst=100),
    "anthropic": RateLimit(requests_per_second=50, burst=200),
    "google_calendar": RateLimit(requests_per_second=10, burst=40),
}

_circuit_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(provider: str) -> CircuitBreaker:
    if provider not in _circuit_breakers:
        _circuit_breakers[provider] = CircuitBreaker()
    return _circuit_breakers[provider]
