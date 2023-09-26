#
# collection of testcases, for leds in linux
# may go into mainline
#
import tbot
import time
from typing import List
from tbot.machine import linux
from tbot.context import Optional


@tbot.testcase
def lnx_test_led_simple(
    lnx: Optional[linux.LinuxShell] = None,
    leds: List[dict] = None,
) -> None:
    """
    simple linux led test. Looks if led file 'brightness' has after boot the
    'bootval' value, than sets the 'onval' value, checks if 'brightness'
    file has now this value, and set it back to 'bootval'.

    simple ... may we can check gpio register, or i2c gpio expander value...
    perfect would be to recognize the led through a webcam...

    :param lab: linux machine we work on
    :param lnx: board linux machine
    :param leds: List of dictionary, see below

    .. code-block:: python

        leds = [
            {"path":"/sys/class/leds/led_blue", "bootval":"0", "onval":"1"},
            ]

    """
    if leds is None:
        raise RuntimeError("please configure leds")

    with tbot.ctx() as cx:
        if lnx is None:
            lnx = cx.request(tbot.role.BoardLinux)

        for led in leds:
            bp = f'{led["path"]}/brightness'
            out = lnx.exec0("cat", bp)
            if led["bootval"] not in out:
                raise RuntimeError(f'{led["bootval"]} not found in {out}')

            lnx.exec0("echo", led["onval"], linux.Raw(">"), bp)

            time.sleep(1)

            out = lnx.exec0("cat", bp)
            if led["onval"] not in out:
                raise RuntimeError(f'{led["onval"]} not found in {out}')

            lnx.exec0("echo", led["bootval"], linux.Raw(">"), bp)
