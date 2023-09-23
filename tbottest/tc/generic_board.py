import tbot
from tbot.machine import linux
from tbot.context import Optional

from tbottest.boardgeneric import cfggeneric
from tbottest.tc.common import lnx_check_beeper
from tbottest.tc.common import lnx_check_dmesg
from tbottest.tc.kas import KAS
from tbottest.tc.leds import lnx_test_led_simple

cfg = cfggeneric


@tbot.testcase
def generic_lnx_test_beep(
    lnx: Optional[linux.LinuxShell] = None,
) -> None:  # noqa: D107
    """
    prerequisite: Board boots into linux

    make a beep

    :param lnx: linux machine where we run

    Uses config variable beep from BOARDNAME.ini

    beep -- array of dictionary with infos for beeping

    .. code-block:: python

        beep = [{"freq": "440", "length":"1000"}]
    """
    with tbot.ctx() as cx:
        if lnx is None:
            lnx = cx.request(tbot.role.BoardLinux)

        lnx_check_beeper(lnx, cfg.beep)


@tbot.testcase
def generic_lnx_test_dmesg(
    lnx: Optional[linux.LinuxShell] = None,
) -> None:  # noqa: D107
    """
    prerequisite: Board boots into linux

    call lnx_check_dmesg() which checks dmesg output.

    :param lnx: Linux machine we run on

    Uses config variables:

    dmesg       -- list of strings which must be in dmesg output
    dmesg_false -- list of strings which does not appear in dmesg output

    .. code-block:: python

        dmesg = [
            "remoteproc remoteproc0: remote processor wkup_m3 is now up",
           ]

        dmesg_false = [
           "crash",
           ]
    """
    with tbot.ctx() as cx:
        if lnx is None:
            lnx = cx.request(tbot.role.BoardLinux)

        ret = lnx_check_dmesg(lnx, cfg.dmesg, cfg.dmesg_false)
        if not ret:
            raise RuntimeError("Error in dmesg output")


@tbot.testcase
def generic_lnx_test_led(
    lnx: Optional[linux.LinuxShell] = None,
) -> None:  # noqa: D107
    """
    prerequisite: Board boots into linux

    switch on and off all leds in list cfg.leds

    uses lnx_test_led_simple(), see more info there

    :param lnx: Linux machine we run on

    Uses config variables:
    leds -- array of dictionary with infos for leds

    .. code-block:: python

        leds = [
            {"path":"/sys/class/leds/led-orange", "bootval":"0", "onval":"1"},
        ]
    """
    with tbot.ctx() as cx:
        if lnx is None:
            lnx = cx.request(tbot.role.BoardLinux)

        lnx_test_led_simple(lab, lnx, cfg.leds)


##############################################################
# kas
##############################################################
@tbot.testcase
def generic_kas_get_config(
    lab: Optional[linux.LinuxShell] = None, bh: Optional[linux.LinuxShell] = None,
) -> None:
    """
    return current kas configuration

    :param lab: Lab Linux machine
    :param bh: Build host machine
    :return: KAS config
    """
    with tbot.ctx() as cx:
        if lab is None:
            lab = cx.request(tbot.role.LabHost)

        if bh is None:
            bh = cx.request(tbot.role.BuildHost)

        cfg.kas["labhost"] = lab
        cfg.kas["buildhost"] = bh

        kas = KAS(cfg.kas)
        return kas


@tbot.testcase
def generic_kas_checkout(
    lab: Optional[linux.LinuxShell] = None, bh: Optional[linux.LinuxShell] = None,
) -> None:
    """
    checks out all yocto layer we need for our yocto build
    with the help of the kas tool.

    See more in KAS class for configuration.

    :param lab: Lab Linux machine
    :param bh: Build host machine
    """
    if "kasskipcheckout" in tbot.flags:
        tbot.log.message(tbot.log.c(f"skip kas checkout step").green)
        return

    with tbot.ctx() as cx:
        if lab is None:
            lab = cx.request(tbot.role.LabHost)

        if bh is None:
            bh = cx.request(tbot.role.BuildHost)

        cfg.kas["labhost"] = lab
        cfg.kas["buildhost"] = bh

        kas = KAS(cfg.kas)
        kas.kas_checkout()


@tbot.testcase
def generic_kas_build(
    lab: Optional[linux.LinuxShell] = None, bh: Optional[linux.LinuxShell] = None,
) -> None:
    """
    build all targets defined in kas configuration

    See more in KAS class for configuration.

    :param lab: Lab Linux machine
    :param bh: Build host machine
    """
    with tbot.ctx() as cx:
        if lab is None:
            lab = cx.request(tbot.role.LabHost)

        if bh is None:
            bh = cx.request(tbot.role.BuildHost)

        cfg.kas["labhost"] = lab
        cfg.kas["buildhost"] = bh
        kas = KAS(cfg.kas)

        # build all targets
        kas.kas_build()


@tbot.testcase
def generic_kas_check_build(
    lab: Optional[linux.LinuxShell] = None, bh: Optional[linux.LinuxShell] = None,
) -> None:
    """
    check if oe build finished, if all files listed in kas_check_files
    exist in deploypath

    :param lab: Lab Linux machine
    :param bh: Build host machine

    Uses config variables:
    kas_check_files    -- array of files which must exist

    .. code-block:: python

        kas_check_files = [
           "tmp/deploy/images/${default:machine}/SPL",
           "tmp/deploy/images/${default:machine}/u-boot.img",
           "tmp/deploy/images/${default:machine}/fitImage",
           "tmp/deploy/sdk/${default:sdk_bin}",
           ]

    """
    with tbot.ctx() as cx:
        if lab is None:
            lab = cx.request(tbot.role.LabHost)

        if bh is None:
            bh = cx.request(tbot.role.BuildHost)

        cfg.kas["labhost"] = lab
        cfg.kas["buildhost"] = bh
        kas = KAS(cfg.kas)

        bp = kas.kas_get_buildpath()

        for f in cfg.kas_check_files:
            bh.exec0("ls", bp / f)


@tbot.testcase
def generic_kas_copy(
    lab: Optional[linux.LinuxShell] = None, bh: Optional[linux.LinuxShell] = None,
) -> linux.Path:
    """
    simply copy all files listed in kas_results from our build host
    to our lab host.

    :param lab: Lab Linux machine
    :param bh: Build host machine

    Uses config variables:
    kas_results -- list of files

    .. code-block:: python

        kas_results = [
           "tmp/deploy/images/${default:machine}/SPL",
           "tmp/deploy/images/${default:machine}/u-boot.img",
           "tmp/deploy/images/${default:machine}/fitImage",
        ]
    """
    with tbot.ctx() as cx:
        if lab is None:
            lab = cx.request(tbot.role.LabHost)

        if bh is None:
            bh = cx.request(tbot.role.BuildHost)

        cfg.kas["labhost"] = lab
        cfg.kas["buildhost"] = bh
        kas = KAS(cfg.kas)

        path = kas.kas_copy(cfg.kas_results)
        return path


@tbot.testcase
def generic_kas_all(
    lab: Optional[linux.LinuxShell] = None, bh: Optional[linux.LinuxShell] = None,
) -> None:
    """
    simply do all build task in one testcase

    Calls:

        | generic_kas_checkout(lab, bh)
        | generic_kas_build(lab, bh)
        | generic_kas_check_build(lab, bh)
        | generic_kas_copy(lab, bh)

    :param lab: Lab Linux machine
    :param bh: Build host machine
    """
    with tbot.ctx() as cx:
        if lab is None:
            lab = cx.request(tbot.role.LabHost)

        if bh is None:
            bh = cx.request(tbot.role.BuildHost)

        generic_kas_checkout(lab, bh)
        generic_kas_build(lab, bh)
        generic_kas_check_build(lab, bh)
        generic_kas_copy(lab, bh)

FLAGS = {
    "kasskipcheckout": "skip kas checkout step",
}
