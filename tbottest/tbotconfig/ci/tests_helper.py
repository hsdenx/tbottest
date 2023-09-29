import tbot
import importlib

from typing import List


FAILED = True
SUCCESS = False


def run_all_tests(tests: List, modname: str, name: str) -> bool:  # noqa: D107
    """
    start all tests from List tests
    """
    failedtest = []
    module = importlib.import_module(modname)
    for test in tests:
        try:
            func = getattr(module, test)
            ret = func()
            if ret is not SUCCESS:
                failedtest.append(test)
        except:
            tbot.log.message(tbot.log.c(f"exception when calling function {test}").red)
            failedtest.append(test)

    if failedtest:
        tbot.log.message(tbot.log.c(f"Failed {name} tests {test}").red)
        return FAILED

    return SUCCESS
