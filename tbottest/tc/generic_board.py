import tbot
from tbot.machine import linux
from tbot.context import Optional

from tbottest.boardgeneric import cfggeneric
from tbottest.tc.common import lnx_check_beeper
from tbottest.tc.common import lnx_check_cmd
from tbottest.tc.common import lnx_check_dmesg
from tbottest.tc.common import lnx_check_revfile
from tbottest.tc.common import lnx_create_revfile
from tbottest.tc.network import lnx_network_ping
from tbottest.tc.network import network_linux_iperf
from tbottest.tc.kas import KAS
from tbottest.tc.leds import lnx_test_led_simple
from tbottest.tc.generictestdef import TC_SKIP, TC_FAIL, TC_OKAY, require_cfg

cfg = cfggeneric


@tbot.testcase
def generic_lnx_check_dump_files(
    lnx: Optional[linux.LinuxShell] = None,
) -> None:  # noqa: D107
    """
    prerequisite: Board boots into linux

    compares for all register dumped into ``revfile`` if they have the
    same value on linux machine lnx. Register values are read with devmem2 tool.

    You can configure a ``difffile`` to which found differences are written.

    :param lnx: linux machine where we run

    Uses config variable lnx_dump_files from section TC_DUMPFILES_BOARDNAME in BOARDNAME.ini

    lnx_dump_files -- array of dictionary with configuration for lnx_check_revfile, see

    :py:func:`tbottest.tc.generic_board.generic_lnx_create_dump_files`
    """
    with tbot.ctx() as cx:
        if lnx is None:
            lnx = cx.request(tbot.role.BoardLinux)

        if len(cfg.lnx_dump_files) == 0:
            return

        for config in cfg.lnx_dump_files:
            lnx_check_revfile(
                lnx, config["revfile"], config["difffile"], config["timeout"]
            )


@tbot.testcase
def generic_lnx_create_dump_files(
    lnx: Optional[linux.LinuxShell] = None,
) -> None:  # noqa: D107
    """
    prerequisite: Board boots into linux

    create a register dump file with name ``revfile`` from ``startaddr`` to ``endaddr``
    with the devmem2 tool. You find the register file in subdir ``tbotconfig/BOARDNAME/files/dumpfiles``

    You need to create this subdir before starting this testcase

    Once created this register dump file it can be used with testcase

    :py:func:`tbottest.tc.generic_board.generic_lnx_check_dump_files`

    which will check if all register still have the same value. so for example
    dump for your current linux kernel the pinmux registers into a dump file
    and after upgrading to a new linux kernel you can be sure that all pinmux
    registers stil have the same value!

    :param lnx: linux machine where we run

    Uses config variable lnx_dump_files from section TC_DUMPFILES_BOARDNAME in BOARDNAME.ini

    lnx_dump_files -- array of dictionary with configuration for lnx_check_revfile

    .. code-block:: python

        lnx_dump_files = [{"revfile":"name of revfile", \n
                "startaddr":"startaddress of dump", \n
                "endaddr":"endaddress of dump", \n
                "mask":"0xffffffff", \n
                "readtype":"readtype of devmem2 command", \n
                "difffile":"file which gets created when there are differences (Set to None to disable it)", \n
                "timeout":"timeout between devmem2 calls (set to None to disable it)" \n
                }]

    example:

    .. code-block:: ini

        [TC_DUMPFILES_BOARDNAME]
        lnx_dump_files = [{"revfile":"control_module.reg", "startaddr":"0x44e10800", "endaddr":"0x44e10808", "mask":"0xffffffff", "readtype":"w", "difffile":"None", "timeout":"None"}]

    creates in tbotconfig/BOARDNAME/files/dump the file control_module.reg with content

    .. code-block:: bash

        $ cat tbotconfig/BOARDNAME/files/dumpfiles/control_module.reg
        # pinmux
        # processor: ToDo
        # hardware : ToDo
        # Linux    : Linux xxx-board 5.15.105-stable-standard #1 PREEMPT Thu Mar 30 10:48:01 UTC 2023 armv7l armv7l armv7l GNU/Linux
        # regaddr mask type defval
        0x44e10800 0xffffffff          w 0x00000031
        0x44e10804 0xffffffff          w 0x00000031


    """
    with tbot.ctx() as cx:
        if lnx is None:
            lnx = cx.request(tbot.role.BoardLinux)

        if len(cfg.lnx_dump_files) == 0:
            return

        for config in cfg.lnx_dump_files:
            lnx_create_revfile(
                lnx,
                config["revfile"],
                config["startaddr"],
                config["endaddr"],
                config["mask"],
                config["readtype"],
            )


@tbot.testcase
@require_cfg(cfg.iperf)
def generic_lnx_network_iperf(
    lab: linux.LinuxShell = None,
    lnx: Optional[linux.LinuxShell] = None,
) -> None:  # noqa: D107
    """
    prerequisite: Board boots into linux

    wrapper for network_linux_iperf with ini file configuration

    :param lnx: linux machine where we run

    iperf -- array of dictionary with infos for network_linux_iperf test

    .. code-block:: python

        ping = [{"ip":"${default:serverip}","retry":"10"}]
    """
    with tbot.ctx() as cx:
        if lab is None:
            lab = cx.request(tbot.role.LabHost)

        if lnx is None:
            lnx = cx.request(tbot.role.BoardLinux)

        si = cfg.get_default_config("serverip", "None")
        ipaddr = cfg.get_default_config("ipaddr", "None")
        for run in cfg.iperf:
            tbot.log.message(tbot.log.c(f"---- start iperf test with server on lab host ----").green)
            network_linux_iperf(lnx, lab, si,run["intervall"], run["cycles"], run["minval"])
            tbot.log.message(tbot.log.c(f"---- start iperf test with server on board ----").green)
            network_linux_iperf(lab, lnx, ipaddr, run["intervall"], run["cycles"], run["minval"])


@tbot.testcase
@require_cfg(cfg.ping)
def generic_lnx_network_ping(
    lnx: Optional[linux.LinuxShell] = None,
) -> None:  # noqa: D107
    """
    prerequisite: Board boots into linux

    simple ping test

    :param lnx: linux machine where we run

    ping -- array of dictionary with infos for ping

    .. code-block:: python

        ping = [{"ip":"${default:serverip}","retry":"10"}]
    """

    with tbot.ctx() as cx:
        if lnx is None:
            lnx = cx.request(tbot.role.BoardLinux)

        for pings in cfg.ping:
            lnx_network_ping(lnx, pings["ip"], int(pings["retry"]))

@tbot.testcase
@require_cfg(cfg.beep)
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
@require_cfg(cfg.lnx_commands)
def generic_lnx_commands(
    lnx: Optional[linux.LinuxShell] = None,
) -> None:  # noqa: D107
    """
    prerequisite: Board boots into linux

    :param lnx: Linux machine we run on

    Uses config variables:

    lnx_commands -- list of dictionary, see below

    .. code-block:: python

        lnx_commands = [
           {"cmd":"linux command", "val":"string commandoutput, 'undef' if none"},
           ]
    """
    with tbot.ctx() as cx:
        if lnx is None:
            lnx = cx.request(tbot.role.BoardLinux)

        ret = lnx_check_cmd(lnx, cfg.lnx_commands)
        if not ret:
            raise RuntimeError("Error in dmesg output")


@tbot.testcase
@require_cfg(cfg.dmesg)
def generic_lnx_test_dmesg(
    lnx: Optional[linux.LinuxShell] = None,
) -> str:  # noqa: D107
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

    return TC_OKAY

@tbot.testcase
@require_cfg(cfg.leds)
def generic_lnx_test_led(
    lnx: Optional[linux.LinuxShell] = None,
) -> str:  # noqa: D107
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

        lnx_test_led_simple(lnx, cfg.leds)

    return TC_OKAY

lnxtestcases = [
    "generic_lnx_network_iperf",
    "generic_lnx_network_ping",
    "generic_lnx_test_beep",
    "generic_lnx_commands",
    "generic_lnx_test_dmesg",
    "generic_lnx_test_led",
]


@tbot.testcase
def generic_lnx_all(
    lnx: Optional[linux.LinuxShell] = None,
) -> None:  # noqa: D107
    """
    start all configured linux testcases
    """
    count = 0
    failed = []
    success = []
    skipped = []

    for tc in lnxtestcases:
        count += 1
        tbot.log.message(tbot.log.c(f"start tc {tc}").green)
        try:
            func = eval(tc)
            ret = func()
            tbot.log.message(tbot.log.c(f"tc {tc} return {ret}").yellow)
            if ret == TC_SKIP:
                skipped.append(tc)
                tbot.log.message(tbot.log.c(f"tc {tc} skipped").yellow)
            else:
                success.append(tc)
                tbot.log.message(tbot.log.c(f"tc {tc} success").green)
        except:
            failed.append(tc)
            tbot.log.message(tbot.log.c(f"tc {tc} failed").red)

    tbot.log.message(tbot.log.c(f"tc count {count} success {len(success)} skipped {len(skipped)} failed {len(failed)}").green)
    if len(skipped):
        tbot.log.message(tbot.log.c(f"skipped {skipped}").yellow)
    if len(failed):
        tbot.log.message(tbot.log.c(f"failed {failed}").red)

##############################################################
# kas
##############################################################
@tbot.testcase
def generic_kas_get_config(
    lab: Optional[linux.LinuxShell] = None,
    bh: Optional[linux.LinuxShell] = None,
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
    lab: Optional[linux.LinuxShell] = None,
    bh: Optional[linux.LinuxShell] = None,
) -> None:
    """
    checks out all yocto layer we need for our yocto build
    with the help of the kas tool.

    See more in KAS class for configuration.

    :param lab: Lab Linux machine
    :param bh: Build host machine
    """
    if "kasskipcheckout" in tbot.flags:
        tbot.log.message(tbot.log.c("skip kas checkout step").green)
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
    lab: Optional[linux.LinuxShell] = None,
    bh: Optional[linux.LinuxShell] = None,
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
    lab: Optional[linux.LinuxShell] = None,
    bh: Optional[linux.LinuxShell] = None,
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
    lab: Optional[linux.LinuxShell] = None,
    bh: Optional[linux.LinuxShell] = None,
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
    lab: Optional[linux.LinuxShell] = None,
    bh: Optional[linux.LinuxShell] = None,
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
