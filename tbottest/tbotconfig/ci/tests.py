import tbot
import importlib


tests = [
    {"module": "tbotconfig.ci.testlab", "func": "laball"},
    {"module": "tbotconfig.ci.testub", "func": "uball"},
    {"module": "tbotconfig.ci.testlnx", "func": "lnxall"},
    {"module": "tbotconfig.ci.testbh", "func": "bhall"},
]


@tbot.testcase
def all() -> str:  # noqa: D107
    """
    start all tests
    """
    failedtest = []
    for test in tests:
        module = importlib.import_module(test["module"])
        try:
            func = getattr(module, test["func"])
            ret = func()
            if ret is not True:
                failedtest.append("laball")
        except:
            tbot.log.message(
                tbot.log.c(
                    f'exception when calling function {test["func"]} from module {test["module"]}'
                ).red
            )
            failedtest.append(test["func"])

    if failedtest:
        tbot.log.message(tbot.log.c(f"Failed {failedtest}").red)
        return False

    return True
