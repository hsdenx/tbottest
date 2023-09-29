import tbot
from tbottest.boardgeneric import cfggeneric
from tbotconfig.ci.tests_helper import run_all_tests, FAILED, SUCCESS


@tbot.testcase
def check_environment_settings() -> bool:  # noqa: D107
    """
    Test if U-Boot environment settings defined in
    ub_env are set.

    uboot_autoboot_keys setting working

    :return: True if Failure, False if no error detected
    """
    with tbot.ctx() as cx:
        ub = cx.request(tbot.role.BoardUBoot)

        error = SUCCESS
        ubenvcfg = eval(cfggeneric.cfgp.get("TC", "ub_env"))
        for entry in ubenvcfg:
            val = ub.env(entry["name"])
            if val not in entry["val"]:
                tbot.log.message(
                    tbot.log.c(f"{entry['name']} not correct in U-Boot environment").red
                )
                error = FAILED

        return error

    return FAILED


ub_tests = {
    "check_environment_settings",
}


@tbot.testcase
def uball() -> bool:  # noqa: D107
    """
    start all U-Boot tests
    """
    return run_all_tests(ub_tests, "tbotconfig.ci.testub", "U-Boot")
