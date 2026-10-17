import tbot
from functools import wraps

TC_SKIP = "skipped"
TC_FAIL = "failed"
TC_OKAY = "okay"


def require_cfg(get_flag, msg=None):
    """
    Decorator for a testcase that needs a value of the board configuration.

    If the value is false (``None``, an empty string, an empty list, ...),
    the testcase is not run. It logs ``msg`` or ``<testcase> not
    configured`` and returns ``TC_SKIP``, which
    :py:func:`tbottest.tc.generic_board.generic_lnx_all` counts as skipped.

    The value is taken when the decorator is applied, i.e. when the module
    is imported, e.g. ``@require_cfg(cfg.dmesg)``.

    :param get_flag: value of the board configuration the testcase needs
    :param msg: optional message instead of ``<testcase> not configured``
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not get_flag:
                text = msg or f"{func.__name__} not configured"
                tbot.log.message(tbot.log.c(text).yellow)
                return TC_SKIP
            return func(*args, **kwargs)
        return wrapper
    return decorator
