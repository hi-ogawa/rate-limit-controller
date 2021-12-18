import asyncio
import functools
import random
from asyncio import Event
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Awaitable, Callable, Optional, TypeVar

F = TypeVar("F")


@dataclass
class RateLimitController:
    rate: int
    last: Optional[Event] = None

    async def context_before(self) -> None:
        last = self.last
        curr = self.last = Event()
        if last:
            await last.wait()
        await asyncio.sleep(1 / self.rate)
        curr.set()

    @asynccontextmanager
    async def context(self) -> AsyncGenerator[None, None]:
        await self.context_before()
        yield


@dataclass
class ResourceScheduler:
    def __init__(self, resources: list[tuple[Any, int]]) -> None:
        self.resources = resources
        self.controllers = [RateLimitController(rate) for _, rate in resources]
        self.rng = random.Random(0xDEF1BABE)

    def choose_resource_index(self) -> int:
        population = range(len(self.resources))
        weights = [float(rate) for _, rate in self.resources]
        chosen = self.rng.choices(population, weights)
        return chosen[0]

    @asynccontextmanager
    async def context(self) -> AsyncGenerator[None, Any]:
        i = self.choose_resource_index()
        resource, _ = self.resources[i]
        controller = self.controllers[i]
        async with controller.context():
            yield resource

    def decorate(self, f: Callable[[Any], Callable[..., Any]]) -> Callable[..., Any]:
        @functools.wraps(f)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            async with self.context() as resource:
                return await (f(resource)(*args, **kwargs))

        return wrapper


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
