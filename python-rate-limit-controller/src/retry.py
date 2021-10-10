import asyncio
import functools
from collections.abc import Coroutine
from typing import Any, Callable, Optional, TypeVar, cast

F = TypeVar("F", bound=Callable[..., Coroutine[None, None, Any]])

# TODO: should be delicate about `CancelledError`


def retry(
    exceptions: tuple[type, ...] = (Exception,),  # is this covariant?
    tries: int = 10,
    delay: float = 1,
    backoff: float = 2,
    on_retry: Optional[Callable[..., None]] = None,
) -> Callable[[F], F]:
    def decorate(f: F) -> F:
        @functools.wraps(f)
        async def wrapper(*args, **kwargs):  # type: ignore[no-untyped-def]
            current_delay = delay
            for i in range(tries):
                try:
                    result = await f(*args, **kwargs)
                    break
                except BaseException as e:  # pylint: disable=broad-except
                    if not isinstance(e, exceptions) or i + 1 == tries:
                        raise
                    if on_retry is not None:
                        on_retry(e)
                await asyncio.sleep(current_delay)
                current_delay *= backoff
            return result

        return cast(F, wrapper)

    return decorate
