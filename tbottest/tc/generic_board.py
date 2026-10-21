import tbot
from tbot.machine import linux
from tbot.context import Optional

from tbottest.boardgeneric import cfggeneric
from tbottest.labgeneric import cfgt as cfglab
import tbottest.initconfig as ini
from tbottest.tc.common import lnx_check_beeper
from tbottest.tc.common import lnx_check_cmd
from tbottest.tc.common import lnx_check_dmesg
from tbottest.tc.common import lnx_check_revfile
from tbottest.tc.common import lnx_cmd_versions
from tbottest.tc.common import lnx_create_revfile
from tbottest.tc.common import lx_devmem2_get
from tbottest.tc.cpu import generic_get_socname
from tbottest.tc.network import lnx_network_ping
from tbottest.tc.network import network_linux_iperf
from tbottest.tc.kas import KAS
from tbottest.tc.leds import lnx_test_led_simple
from tbottest.tc.can import board_lnx_cangen, cangen_config_calls
from tbottest.tc.rs485 import board_lnx_rs485, rs485_config_kwargs
from tbottest.tc.generictestdef import TC_SKIP, TC_FAIL, TC_OKAY, require_cfg, tc_config
from tbottest.tc.registermap import REGISTERMAP

cfg = cfggeneric


@tbot.testcase
@tc_config
def generic_lnx_check_dump_files(
    lnx: Optional[linux.LinuxShell] = None,
) -> None:  # noqa: D107
    """
    prerequisite: Board boots into linux

    compares for all register dumped into ``revfile`` if they have the
    same value on linux machine lnx. Register values are read with devmem2 tool.

    You can configure a ``difffile`` to which found differences are written.

    :param lnx: linux machine where we run

    Uses key lnx_dump_files of the board configuration

    lnx_dump_files -- array of dictionary with configuration for lnx_check_revfile, see

    :py:func:`tbottest.tc.generic_board.generic_lnx_create_dump_files`
    """
    with tbot.ctx() as cx:
        if lnx is None:
            lnx = cx.request(tbot.role.BoardLinux)

        dump_files = cfg.get_lnx_dump_files()
        if len(dump_files) == 0:
            return

        for config in dump_files:
            lnx_check_revfile(
                lnx, config["revfile"], config["difffile"], config["timeout"]
            )


@tbot.testcase
@tc_config
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

    Uses key lnx_dump_files of the board configuration

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

        dump_files = cfg.get_lnx_dump_files()
        if len(dump_files) == 0:
            return

        for config in dump_files:
            lnx_create_revfile(
                lnx,
                config["revfile"],
                config["startaddr"],
                config["endaddr"],
                config["mask"],
                config["readtype"],
            )

@tbot.testcase
@require_cfg("regdump")
def generic_lx_dump_register(
    lnx: Optional[linux.LinuxShell] = None,
) -> bool:  # noqa: D107
    """
    Create a register dump on lnx machine, and
    save it on local hosts workdir in file "generic_registerdump.txt"

    :param lnx: Linux machine we run on

    Uses config variables:

    regdump -- list of dictionary

    .. code-block:: python

        regdump = [{"address":"0x30340004"}, {"address":"0x30330070"}]
    """
    with tbot.ctx() as cx:
        if lnx is None:
            lnx = cx.request(tbot.role.BoardLinux)

        local = cx.request(tbot.role.LocalHost)
        sourcepath = local.sourcedir()._local_str()
        workpath = local.workdir()._local_str()
        socname = generic_get_socname(lnx)
        if "not detected" in socname:
            tbot.log.message(tbot.log.c(f"SoC not detected, please add in generic_get_socname").yellow)
            return TC_SKIP

        name = f"{socname}_registers.json"
        registerfilepath = f"{sourcepath}/scripts/registermap/{name}"
        regmap = REGISTERMAP(registerfilepath)
        outputpath = f"{workpath}/generic_registerdump.txt"
        local.exec0("rm", "-rf", outputpath)
        for dump in cfg.get_config_literal("regdump", "[]"):
            address = dump["address"]
            #val = ub_read_register(ub, address)
            val = lx_devmem2_get(lnx, address, "w")
            regmap.registermap_dump_register_file(outputpath, address, val)

        tbot.log.message(tbot.log.c(f"Register dumped to file {outputpath}").green)


@tbot.testcase
@require_cfg("iperf")
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
        for run in cfg.get_config_literal("iperf", "[]"):
            tbot.log.message(tbot.log.c(f"---- start iperf test with server on lab host ----").green)
            network_linux_iperf(lnx, lab, si,run["intervall"], run["cycles"], run["minval"])
            tbot.log.message(tbot.log.c(f"---- start iperf test with server on board ----").green)
            network_linux_iperf(lab, lnx, ipaddr, run["intervall"], run["cycles"], run["minval"])


@tbot.testcase
@require_cfg("ping")
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

        for pings in cfg.get_config_literal("ping", "[]"):
            lnx_network_ping(lnx, pings["ip"], int(pings["retry"]))

@tbot.testcase
@require_cfg("beep")
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

        lnx_check_beeper(lnx, cfg.get_config_literal("beep", "[]"))


@tbot.testcase
@require_cfg("lnx_commands")
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
           {"mode":"exec", "cmd":"systemctl --all stop my-service"},
           ]

    An entry without "val" only runs its command; with "mode": "exec"
    its return code does not matter, see
    :py:func:`tbottest.tc.common.lnx_check_cmd`.
    """
    with tbot.ctx() as cx:
        if lnx is None:
            lnx = cx.request(tbot.role.BoardLinux)

        ret = lnx_check_cmd(lnx, cfg.get_config_literal("lnx_commands", "[]"))
        if not ret:
            raise RuntimeError("Error in dmesg output")


@tbot.testcase
@require_cfg("dmesg")
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

        ret = lnx_check_dmesg(
            lnx,
            cfg.get_config_literal("dmesg", "[]"),
            cfg.get_config_literal("dmesg_false", "[]"),
        )
        if not ret:
            raise RuntimeError("Error in dmesg output")

    return TC_OKAY

@tbot.testcase
@require_cfg("leds")
def generic_lnx_test_led(
    lnx: Optional[linux.LinuxShell] = None,
) -> str:  # noqa: D107
    """
    prerequisite: Board boots into linux

    switch on and off all leds in list leds

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

        lnx_test_led_simple(lnx, cfg.get_config_literal("leds", "[]"))

    return TC_OKAY


@tbot.testcase
@require_cfg("cangen")
def generic_lnx_test_cangen(
    lab: Optional[linux.LinuxShell] = None,
    lnx: Optional[linux.LinuxShell] = None,
) -> str:  # noqa: D107
    """
    prerequisite: Board boots into linux, the lab host has a CAN interface
    on the CAN bus of the board

    sends CAN frames with cangen from the lab host to the board and from
    the board to the lab host, and the receiving side checks what candump
    received, with :py:func:`tbottest.tc.can.board_lnx_cangen`, for every
    entry of cangen (see :py:func:`tbottest.tc.can.cangen_config_calls`)

    :param lab: lab host
    :param lnx: Linux machine of the board

    Uses config variables:
    cangen -- array of dictionary with the keys boarddev and labdev, the
    CAN interfaces of the board and of the lab host, directions, a list of
    lab2board and board2lab (default both), and the parameters tmpdir,
    frames, dllength, bitrate, txqueuelen and cangen_gap of
    board_lnx_cangen, missing ones keep its defaults

    .. code-block:: python

        cangen = [
            {"boarddev": ["can0"], "labdev": ["can0"], "frames": "1000",
             "dllength": "8", "bitrate": "500000"},
        ]

    If other machines are used, you need a board specific implementation
    and call board_lnx_cangen().
    """
    with tbot.ctx() as cx:
        if lab is None:
            lab = cx.request(tbot.role.LabHost)

        if lnx is None:
            lnx = cx.request(tbot.role.BoardLinux)

        for run in cfg.get_config_literal("cangen", "[]"):
            for direction, kwargs in cangen_config_calls(run):
                tbot.log.message(tbot.log.c(f"cangen {direction}").green)
                if direction == "lab2board":
                    board_lnx_cangen(lnx=lnx, lnxsend=lab, **kwargs)
                else:
                    board_lnx_cangen(lnx=lab, lnxsend=lnx, **kwargs)

    return TC_OKAY


@tbot.testcase
@require_cfg("rs485")
def generic_lnx_test_rs485(
    lab: Optional[linux.LinuxShell] = None,
    lnx: Optional[linux.LinuxShell] = None,
) -> int:  # noqa: D107
    """
    prerequisite: Board boots into linux, the lab host has a serial
    interface on the RS485 line of the board

    sends random bytes over RS485 from the lab host to the board and back,
    with :py:func:`tbottest.tc.rs485.board_lnx_rs485`, once for every entry
    of rs485 (see :py:func:`tbottest.tc.rs485.rs485_config_kwargs`)

    :param lab: lab host
    :param lnx: Linux machine of the board

    Uses config variables:
    rs485 -- array of dictionary, the keys are the parameters ethdevice,
    rs485labdev, rs485baud, rs485boarddev, rs485lengths and debug of
    board_lnx_rs485

    .. code-block:: python

        rs485 = [
            {"ethdevice": "eth0",
             "rs485labdev": "/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_AB0PI210-if00-port0",
             "rs485baud": "115200", "rs485boarddev": ["/dev/ttymxc2"],
             "rs485lengths": ["1", "100"]},
        ]
    """
    with tbot.ctx() as cx:
        if lab is None:
            lab = cx.request(tbot.role.LabHost)
        if lnx is None:
            lnx = cx.request(tbot.role.BoardLinux)

        for run in cfg.get_config_literal("rs485", "[]"):
            board_lnx_rs485(lab=lab, lnx=lnx, **rs485_config_kwargs(run))

    return TC_OKAY


lnxtestcases = [
    "generic_lx_dump_register",
    "generic_lnx_network_iperf",
    "generic_lnx_network_ping",
    "generic_lnx_test_beep",
    "generic_lnx_commands",
    "generic_lnx_test_dmesg",
    "generic_lnx_test_led",
    "generic_lnx_test_cangen",
    "generic_lnx_test_rs485",
]


@tbot.testcase
def generic_cmd_versions(
    lab: Optional[linux.LinuxShell] = None,
    lnx: Optional[linux.LinuxShell] = None,
) -> None:  # noqa: D107
    """
    find out which implementation and version the commands tbottest uses
    have on the lab host, the build host (if tbot.ini has one) and the
    board, and log a line for the ini key cmd_versions for each, see
    :py:mod:`tbottest.cmdversions`

    The line for the lab host goes into section [LABHOST] (or
    [LABHOST_<labname>]) of tbot.ini, the one for the build host into its
    section [BUILDHOST] (or [BUILDHOST_<name>]), the one for the board into
    section [TC] (or [TC_<boardname>]) of <boardname>.ini.

    With tbot flag cmd_versions_install missing commands are installed
    where the system can (Debian, Ubuntu, Fedora).

    :param lab: lab host
    :param lnx: linux machine of the board
    """
    autoinstall = "cmd_versions_install" in tbot.flags
    with tbot.ctx() as cx:
        if lab is None:
            lab = cx.request(tbot.role.LabHost)
        tbot.log.message(tbot.log.c("lab host, tbot.ini section [LABHOST]").green)
        lnx_cmd_versions(lab, autoinstall=autoinstall)

        if cfglab.find_sections("BUILDHOST"):
            bh = cx.request(tbot.role.BuildHost)
            tbot.log.message(tbot.log.c(f"build host, tbot.ini section [{bh.sn}]").green)
            lnx_cmd_versions(bh, autoinstall=autoinstall)

        if lnx is None:
            lnx = cx.request(tbot.role.BoardLinux)
        tbot.log.message(tbot.log.c("board, <boardname>.ini section [TC]").green)
        # keys in [TC] of the board ini template are indented
        lnx_cmd_versions(lnx, autoinstall=autoinstall, keyindent="    ")


@tbot.testcase
def generic_config_to_json(outdir: Optional[str] = None) -> None:  # noqa: D107
    """
    write the configuration of this run as tbot.json and <boardname>.json,
    see the JSON configuration in generic.rst

    From an ini configuration, after set_board_cfg() of boardspecific.py
    replaced the placeholders, so the files hold the values of this run
    (e.g. of its flags); replace those with ${flag:...} or ${env:...}
    where a value depends on them. Values keep their ${...} references,
    with the tbot flag config_json_resolved they are written resolved, as
    tbot reads them, to compare two configurations.

    :param outdir: directory for the two files, default the tbot flag
        config_json_dir:<dir>, else config-json in the current directory
    """
    import json
    import os

    if outdir is None:
        outdir = "config-json"
        for f in tbot.flags:
            if f.startswith("config_json_dir:"):
                outdir = f.split(":", 1)[1]
    resolved = "config_json_resolved" in tbot.flags
    os.makedirs(outdir, exist_ok=True)
    for name, cfgp in (
        ("tbot.json", cfglab.config_parser),
        (f"{ini.generic_get_boardname()}.json", cfg.cfgp.config_parser),
    ):
        path = os.path.join(outdir, name)
        with open(path, "w") as f:
            json.dump(ini.init_config_to_json_dict(cfgp, resolved), f, indent=4)
            f.write("\n")
        tbot.log.message(tbot.log.c(f"configuration written to {path}").green)


@tbot.testcase
def generic_lnx_all(
    lnx: Optional[linux.LinuxShell] = None,
) -> None:  # noqa: D107
    """
    start all configured linux testcases

    Runs every testcase of the list ``lnxtestcases`` in this module and
    counts it as

    - skipped, if it returns ``TC_SKIP``, as the testcases decorated with
      :py:func:`tbottest.tc.generictestdef.require_cfg` do when their key
      is not in the board configuration,
    - failed, if it raises an exception,
    - success otherwise.

    At the end it logs the counts and the names of the skipped and the
    failed testcases. It does not raise an exception itself when a
    testcase failed.
    """
    count = 0
    failed = []
    success = []
    skipped = []

    for tc in lnxtestcases:
        count += 1
        tbot.log.message(tbot.log.c(f"start tc {tc}").green)
        try:
            func = globals()[tc]
            ret = func()
            tbot.log.message(tbot.log.c(f"tc {tc} return {ret}").yellow)
            if ret == TC_SKIP:
                skipped.append(tc)
                tbot.log.message(tbot.log.c(f"tc {tc} skipped").yellow)
            else:
                success.append(tc)
                tbot.log.message(tbot.log.c(f"tc {tc} success").green)
        except Exception:
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
@tc_config
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

        kas = KAS(cfg.kas_config(lab, bh))
        return kas


@tbot.testcase
@tc_config
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

        kas = KAS(cfg.kas_config(lab, bh))
        kas.kas_checkout()


@tbot.testcase
@tc_config
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

        kas = KAS(cfg.kas_config(lab, bh))

        # build all targets
        kas.kas_build()


@tbot.testcase
@tc_config
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

        kas = KAS(cfg.kas_config(lab, bh))

        bp = kas.kas_get_buildpath()

        for f in cfg.get_config_literal("kas_check_files", "[]"):
            bh.exec0("ls", bp / f)


@tbot.testcase
@tc_config
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

        kas = KAS(cfg.kas_config(lab, bh))

        path = kas.kas_copy(cfg.get_config_literal("kas_results", "[]"))
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
    "cmd_versions_install": "generic_cmd_versions: install missing commands where possible",
    "config_json_dir": "config_json_dir:<dir> generic_config_to_json: directory for the files",
    "config_json_resolved": "generic_config_to_json: write the values resolved",
    "kasskipcheckout": "skip kas checkout step",
    "kaskeepconfig": (
        "kas: keep repo checkouts and build/conf unchanged (kas "
        "--keep-config-unchanged), needs an earlier run without it"
    ),
}
