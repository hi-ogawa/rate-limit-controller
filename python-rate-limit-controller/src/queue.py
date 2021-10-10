from asyncio import Event
from dataclasses import dataclass, field
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class Queue(Generic[T]):
    xs: list[T] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)

    async def get(self) -> T:
        if len(self.xs) == 0:
            event = Event()
            self.events.append(event)
            await event.wait()
            assert len(self.xs) > 0
        return self.xs.pop(0)

    def put(self, x: T) -> None:
        self.xs.append(x)
        if len(self.events) > 0:
            event = self.events.pop(0)
            event.set()
