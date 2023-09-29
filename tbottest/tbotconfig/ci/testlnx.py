import tbot
import importlib
from tbottest.boardgeneric import cfggeneric
from tbotconfig.ci.tests_helper import run_all_tests, FAILED, SUCCESS


@tbot.testcase
def lnx_test_linux_init_cfg() -> bool:  # noqa: D107
    """
    Test  linux_init_cfg configuration, no idea yet how to check

    :return: True if Failure, False if no error detected
    """
    with tbot.ctx() as cx:
        lnx = cx.request(tbot.role.BoardLinux)

        error = SUCCESS
        linux_init_cfg = eval(cfggeneric.cfgp.get("TC", "linux_init"))
        for entry in linux_init_cfg:
            print(f"Entry {entry}")
        lnx.exec0("echo", "donothing")

        return error

    return FAILED


lnx_generic = [
    "generic_lnx_test_dmesg",
    "generic_lnx_commands",
]


@tbot.testcase
def lnx_test_linux_generic() -> bool:  # noqa: D107
    """
    Test generic testcases

    :return: True if Failure, False if no error detected
    """
    with tbot.ctx() as cx:
        lnx = cx.request(tbot.role.BoardLinux)

        error = SUCCESS
        module = importlib.import_module("tbottest.tc.generic_board")
        for test in lnx_generic:
            try:
                func = getattr(module, test)
                func(lnx)
            except:
                error = FAILED

        return error

    return FAILED


lnx_tests = {
    "lnx_test_linux_init_cfg",
    "lnx_test_linux_generic",
}


@tbot.testcase
def lnxall() -> bool:  # noqa: D107
    """
    start all Linux Board tests
    """
    return run_all_tests(lnx_tests, "tbotconfig.ci.testlnx", "Linux Board")
