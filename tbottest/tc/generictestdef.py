import ast
from functools import wraps

import tbot

import tbottest.initconfig as ini

TC_SKIP = "skipped"
TC_FAIL = "failed"
TC_OKAY = "okay"


def tc_config(func):
    """
    Decorator for a testcase that reads the board configuration.

    While the testcase runs, its name is the current testcase (see
    :py:func:`tbottest.initconfig.init_testcase`), so the configuration is
    searched in the section ``TC_BOARDNAME.TESTCASENAME`` first, see
    :py:func:`tbottest.initconfig.init_get_config`.

    .. code-block:: python

        @tbot.testcase
        @tc_config
        def my_testcase() -> None:
            count = cfggeneric.get_config_int("count", "1")
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        with ini.init_testcase(func.__name__):
            return func(*args, **kwargs)

    return wrapper


def cfg_is_set(value) -> bool:
    """
    returns if a value of the board configuration (a string or None) is
    set. None, an empty string and a Python literal that is false (an
    empty list, an empty dictionary, 0, False) are not set.

    :param value: value as init_get_config() returns it
    """
    if value is None:
        return False
    try:
        return bool(ast.literal_eval(value))
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        return value != ""


def require_cfg(key: str, msg=None):
    """
    Decorator for a testcase that needs a key of the board configuration.

    It does what :py:func:`tc_config` does and reads the key when the
    testcase is called, so a value in ``TC_BOARDNAME.TESTCASENAME`` counts.
    If the key is not set (see :py:func:`cfg_is_set`), the testcase is not
    run. It logs ``msg`` or ``<testcase> not configured`` and returns
    ``TC_SKIP``, which :py:func:`tbottest.tc.generic_board.generic_lnx_all`
    counts as skipped.

    .. code-block:: python

        @tbot.testcase
        @require_cfg("dmesg")
        def generic_lnx_test_dmesg(lnx=None) -> str:
            ...

    :param key: key of the board configuration the testcase needs
    :param msg: optional message instead of ``<testcase> not configured``
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with ini.init_testcase(func.__name__):
                if not cfg_is_set(ini.IniConfig().get_config(key, "None")):
                    text = msg or f"{func.__name__} not configured"
                    tbot.log.message(tbot.log.c(text).yellow)
                    return TC_SKIP
                return func(*args, **kwargs)

        return wrapper

    return decorator
