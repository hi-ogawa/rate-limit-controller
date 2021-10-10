import asyncio
import functools
import random
from collections.abc import AsyncGenerator, Coroutine
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from timeit import default_timer
from typing import Any, Callable, TypeVar, cast

from .queue import Queue

F = TypeVar("F", bound=Callable[..., Coroutine[None, None, Any]])

INF = float("inf")


@dataclass
class Log:
    index: int
    inflight: bool
    begin: float


@dataclass
class RateLimitController:
    rate: int
    interval: float
    interval_jitter: float = 0

    index: int = 0
    logs: list[Log] = field(default_factory=list)
    signal: Queue[None] = field(default_factory=Queue)
    rng: random.Random = random.Random()

    @property
    def inflight_count(self) -> int:
        return sum(int(log.inflight) for log in self.logs)

    async def before(self) -> int:
        while True:
            # Inflight count should be at most `rate`
            assert self.inflight_count <= self.rate

            if self.inflight_count >= self.rate:
                # Wait for the signal of inflight count decrease
                await self.signal.get()

                # Continue waiting
                if self.inflight_count >= self.rate:
                    continue

            # Cleanup unnecessary logs
            t = default_timer()
            self.logs = [
                log
                for log in self.logs
                if log.inflight or log.begin >= t - self.interval - self.interval_jitter
            ]

            # Sleep to satisfy rate limit
            t_last = -INF
            dt_jitter = 0
            if len(self.logs) >= self.rate:
                t_last = self.logs[-self.rate].begin
                dt_jitter = self.rng.uniform(0, self.interval_jitter)
            dt = max(0, t_last + self.interval - t)
            await asyncio.sleep(dt + dt_jitter)

            # Continue waiting
            if self.inflight_count >= self.rate:
                continue

            break

        index = self.index
        self.logs.append(Log(index, inflight=True, begin=default_timer()))
        self.index += 1
        return index

    def after(self, index: int) -> None:
        log = next(filter(lambda log: log.index == index, self.logs))
        log.inflight = False
        self.signal.put(None)

    @asynccontextmanager
    async def limit_context(self) -> AsyncGenerator[None, None]:
        index = await self.before()
        try:
            yield
        finally:
            self.after(index)

    def decorate(self, f: F) -> F:
        @functools.wraps(f)
        async def wrapper(*args, **kwargs):  # type: ignore[no-untyped-def]
            async with self.limit_context():
                return await f(*args, **kwargs)

        return cast(F, wrapper)
