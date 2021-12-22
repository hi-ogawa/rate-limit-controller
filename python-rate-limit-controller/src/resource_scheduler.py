import asyncio
import functools
import random
from asyncio import Event
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, AsyncGenerator, Awaitable, Callable, Generic, TypeVar, cast

F = TypeVar("F", bound=Callable[..., Any])
T = TypeVar("T")


class RateLimitController:
    def __init__(self, rate: int) -> None:
        self.rate = rate
        self.rate_timedelta = timedelta(seconds=1 / rate)
        self.last = Event()
        self.last.set()
        self.last_timestamp = datetime.min

    async def context_before(self) -> None:
        last = self.last
        curr = self.last = Event()
        await last.wait()
        seconds = (self.last_timestamp + self.rate_timedelta - datetime.now()).total_seconds()
        if seconds > 0:
            await asyncio.sleep(seconds)
        self.last_timestamp = datetime.now()
        curr.set()

    @asynccontextmanager
    async def context(self) -> AsyncGenerator[None, None]:
        await self.context_before()
        yield


class ResourceScheduler(Generic[T]):
    def __init__(self, resources: list[tuple[T, int]]) -> None:
        self.resources = resources
        self.controllers = [RateLimitController(rate) for _, rate in resources]
        self.rng = random.Random(0xDEF1BABE)

    def choose_resource_index(self) -> int:
        population = range(len(self.resources))
        weights = [float(rate) for _, rate in self.resources]
        chosen = self.rng.choices(population, weights)
        return chosen[0]

    @asynccontextmanager
    async def context(self) -> AsyncGenerator[T, None]:
        i = self.choose_resource_index()
        resource, _ = self.resources[i]
        controller = self.controllers[i]
        async with controller.context():
            yield resource

    def decorate(self, f: Callable[[T], F]) -> F:
        @functools.wraps(f)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            async with self.context() as resource:
                return await (f(resource)(*args, **kwargs))

        return cast(F, wrapper)


import os
from datetime import datetime

import aiohttp
import aiohttp.web

API_ENDPOINT = "https://api.bscscan.com/api"
APIKYES = os.getenv("APIKEYS").split(",")
RESOURCES = [(key, 4) for key in APIKYES]

scheduler = ResourceScheduler(RESOURCES)

state = dict(counter=0)


def request_with_apikey(
    apikey: str,
) -> Callable[[dict[str, Any]], str]:
    async def inner(params: dict[str, Any]) -> str:
        state["counter"] += 1
        idx = state["counter"]
        beg = datetime.now()
        print(f"[{beg}:BEG] {idx = }")
        params = params | dict(apikey=apikey)
        async with aiohttp.request("GET", API_ENDPOINT, params=params) as resp:
            resp_text = await resp.text()
            resp_json = await resp.json()
            status = resp_json.get("status")
            end = datetime.now()
            diff = (end - beg).total_seconds()
            print(f"[{end}:END] {idx = }, {status = }, {diff = }")
            return resp_text

    return inner


scheduled_request_with_apikey: Callable[[dict[str, Any]], Awaitable[Any]]
scheduled_request_with_apikey = scheduler.decorate(request_with_apikey)


async def get_proxy(req: aiohttp.web.Request) -> aiohttp.web.Response:
    res_text = await scheduled_request_with_apikey(dict(req.url.query))
    return aiohttp.web.json_response(text=res_text)


def main(port: int) -> None:
    app = aiohttp.web.Application()
    app.router.add_get("/bsc/api", get_proxy)
    aiohttp.web.run_app(app, port=port)


if __name__ == "__main__":
    main(8080)
