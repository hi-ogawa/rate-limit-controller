import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Any, cast

import aiohttp

from .rate_limit_controller import RateLimitController
from .retry import retry

RATE = 5
INTERVAL = 1.3
JITTER = 0.2

rate_limit_controller = RateLimitController(RATE, INTERVAL, JITTER)

API_KEY = cast(str, os.getenv("API_KEY"))
API_ENDPOINT = "https://api.bscscan.com/api"
assert API_KEY


def logging(*args: Any) -> None:
    print(*args, file=sys.stderr)


@rate_limit_controller.decorate
@retry(exceptions=(RuntimeError,), on_retry=lambda e: logging("retry: ", e))
async def request(txhash: str) -> dict[str, str]:
    logging(f"BEGIN ({txhash[2:10]})", datetime.now())
    params = dict(
        module="proxy",
        action="eth_getTransactionByHash",
        txhash=txhash,
        apikey=API_KEY,
    )
    async with aiohttp.request("GET", API_ENDPOINT, params=params) as resp:
        logging(f"END   ({txhash[2:10]})", datetime.now())
        if not resp.ok:
            text = await resp.text()
            raise RuntimeError(f"request error: status = {resp.status}, text = {text}")

        resp_json: dict[str, Any] = await resp.json()
        if resp_json.get("status") == "0":
            raise RuntimeError(f"api error: {resp_json}")
        return cast(dict[str, str], resp_json["result"])


async def async_main() -> None:
    data = json.load(sys.stdin)
    hashes: list[str] = [tx["txnHash"] for tx in data["transactions"]]

    # TODO: deal with CancelledError
    results = await asyncio.gather(*map(request, hashes))

    print(json.dumps(results, indent=2, ensure_ascii=False))


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
