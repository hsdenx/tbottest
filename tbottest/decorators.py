import functools
import tbot
import typing

from tbot.machine import linux

F_tc = typing.TypeVar("F_tc", bound=typing.Callable[..., typing.Any])

def tbot_save_flags(tc: F_tc) -> F_tc:
    """
    Use this decorator if your testcase manipulates the tbot flags.

    it ensures, that the tbot.flags are not changed after the testcase
    finishes.
    """
    @functools.wraps(tc)
    def wrapper(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        oldflags = tbot.flags.copy()
        failure = False
        try:
            tc(*args, **kwargs)
        except:
            failure = True

        tbot.flags = oldflags.copy()
        if failure:
            raise RuntimeError(f"{tc} failed")

    return wrapper
