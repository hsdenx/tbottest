import inspect
import time
import re
import tbot
from tbot.machine import board, linux, connector, channel
from typing import List

import os

# import generic lab approach
from tbottest import labgeneric as lab
import tbottest.initconfig as ini
from tbottest.labgeneric import cfgt as cfglab

try:
    from tbotconfig.boardspecific import set_ub_board_specific
except:
    raise RuntimeError("Please define at least a dummy set_ub_board_specific in tbotconfig.boardspecific")
    set_ub_board_specific = None

cfg = ini.IniConfig()

class GenericBoardConfig:
    currentdir = os.path.dirname(
        os.path.abspath(inspect.getfile(inspect.currentframe()))
    )
    workdir = os.path.dirname(currentdir)

    boardname = ini.generic_get_boardname()
    cfgp = cfg.config_parser
    tmpdir = cfgp.get(f"TC", "tmpdir", fallback="/tmp")

    ##############################################
    # Imagenames
    ##############################################
    rescueimage = cfgp.get(f"TC", "rescueimage", fallback=None)
    qspiheader = cfgp.get(f"TC", "qspiheader", fallback=None)
    splimage = cfgp.get(f"TC", "splimage", fallback=None)

    mtd_parts = eval(cfgp.get(f"TC", "mtd_parts", fallback="[]"))
    ub_mtd_delete = eval(cfgp.get(f"TC", "ub_mtd_delete", fallback="[]"))

    ##############################################
    # U-Boot testcases
    ##############################################
    fb_res_setup = cfgp.get(f"TC", "fb_res_setup", fallback=None)
    fb_res_boot = cfgp.get(f"TC", "fb_res_boot", fallback=None)
    fb_cmd = cfgp.get(f"TC", "fb_cmd", fallback=None)

    ##############################################
    # Linux testcases
    ##############################################
    beep = eval(cfgp.get(f"TC", "beep", fallback="[]"))
    cyclictestmaxvalue = eval(cfgp.get(f"TC", "cyclictestmaxvalue", fallback="100"))
    dmesg = eval(cfgp.get(f"TC", "dmesg", fallback="[]"))
    dmesg_false = eval(cfgp.get(f"TC", "dmesg_false", fallback="[]"))
    leds = eval(cfgp.get(f"TC", "leds", fallback="[]"))
    network_iperf_intervall = eval(cfgp.get(f"TC", "network_iperf_intervall", fallback="1"))
    network_iperf_minval = eval(cfgp.get(f"TC", "network_iperf_minval", fallback="90000000"))
    network_iperf_cycles = eval(cfgp.get(f"TC", "network_iperf_cycles", fallback="30"))

    nvramdev = cfgp.get("TC", "nvramdev", fallback=None)
    nvramcomp = cfgp.get("TC", "nvramcomp", fallback=None)
    nvramsz = cfgp.get("TC", "nvramsz", fallback=None)

    rs485labdev = cfgp.get("TC", "rs485labdev", fallback=None)
    rs485baud = cfgp.get("TC", "rs485baud", fallback=None)
    rs485boarddev = eval(cfgp.get("TC", "rs485boarddev", fallback='["/dev/ttymxc2"]'))
    rs485lengths = eval(cfgp.get("TC", "rs485lengths", fallback='["20", "100", "1024"]'))

    sensors = eval(cfgp.get(f"TC", "sensors", fallback="[]"))

    ##############################################
    # swupdate testcases
    ##############################################
    swuethdevice = cfgp.get(f"TC", "swuethdevice", fallback="eth0")
    swuimage = cfgp.get(f"TC", "swuimage", fallback=None)

    ##############################################
    # kas testcases
    ##############################################
    kas = eval(cfgp.get(f"TC", "kas", fallback="[]"))
    kas_check_files = eval(cfgp.get(f"TC", "kas_check_files", fallback="[]"))
    kas_results = eval(cfgp.get(f"TC", "kas_results", fallback="[]"))


cfggeneric = GenericBoardConfig()

BOARD_LINUX_SHELL = linux.Ash
#BOARD_LINUX_SHELL = linux.Bash

class GenericUBoot(
    board.Connector, board.UBootAutobootInterceptSimple, board.UBootShell
):  # noqa: E501
    cfgp = cfg.config_parser
    name = f"{ini.generic_get_boardname()}-uboot"
    prompt = cfgp.get(f"TC", "uboot_prompt", fallback="=> ")
    # remove ""
    prompt = prompt.strip('"')

    # If U-Boot is not up after 90 seconds, something is seriously wrong
    # we must use here 90 seconds as wdt timeout is 90 seconds.
    bt = cfgp.get(f"TC", "uboot_boot_timeout", fallback=90)
    if bt == "None":
        boot_timeout = None
    else:
        boot_timeout = int(bt)

    ap = cfgp.get(f"TC", "uboot_autoboot_prompt", fallback=b"autoboot:\s{0,5}\d{0,3}\s{0,3}.{0,80}")
    if ap == "None":
        autoboot_prompt = None
    else:
        autoboot_prompt = tbot.Re(ap, re.DOTALL)

    ap = cfgp.get(f"TC", "uboot_autoboot_timeout", fallback="0.1")
    if ap == "None":
        autoboot_timeout = 0.1
    else:
        autoboot_timeout = float(ap)

    ap = cfgp.get(f"TC", "uboot_autoboot_keys", fallback="None")
    if ap == "None":
        autoboot_keys = None
    elif ap == "SPACE":
        autoboot_keys = " "
    else:
        autoboot_keys = str(ap)

    ap = cfgp.get(f"TC", "uboot_autoboot_iter", fallback="None")
    if ap == "None":
        pass
    else:
        autoboot_iter = int(ap)

    def get_death_strings(self) -> List[str]:
        return eval(cfg.config_parser.get(f"TC", "uboot_death_strings", fallback="[]"))

    def init(self) -> None:
        if "uboot_no_env_set" in tbot.flags:
            return

        if "set-ethconfig" in tbot.flags:
            try:
                intf = cfglab.ubcfg[ini.generic_get_boardname()]["ethintf"]
            except:  # noqa: E722
                intf = "eth0"

            ethdev = cfglab.ethdevices[ini.generic_get_boardname()][intf]
            self.env("ipaddr", ethdev["ipaddr"])
            self.env("serverip", ethdev["serverip"])
            self.env("netmask", ethdev["netmask"])
            self.env("ethaddr", ethdev["ethaddr"])
            self.env("date", cfglab.date)

        if "ignore_loglevel" in tbot.flags:
            out = self.exec0("printenv", "miscargs").strip()
            out = out + " ignore_loglevel"
            self.env("miscargs", out)
        if "enterinitramfs" in tbot.flags:
            out = self.exec0("printenv", "miscargs").strip()
            out = out + " enterinitramfs"
            self.env("miscargs", out)

        if "nobootcon" in tbot.flags:
            self.env("console", "silent")

        env = self.cfgp.get("TC", "ub_env", fallback="[]")
        envvalues = eval(env)
        for ev in envvalues:
            self.env(ev["name"], ev["val"])

        if set_ub_board_specific:
            set_ub_board_specific(self)

def add_death_strings(ch):
    dstr = eval(cfg.config_parser.get(f"TC", "death_strings", fallback="[]"))
    for m in dstr:
        ch.add_death_string(m)

class GenericLinuxBoot(board.LinuxUbootConnector, board.LinuxBootLogin, BOARD_LINUX_SHELL):
    name = f"{ini.generic_get_boardname()}-linux"

    uboot = GenericUBoot

    cfgp = cfg.config_parser
    username = cfgp.get(f"TC", "linux_user", fallback="root")
    pwd = cfgp.get(f"TC", "linux_password", fallback="None")
    if pwd == "None":
            password = None
    else:
            password = pwd

    bt = cfgp.get(f"TC", "linux_login_delay", fallback=None)
    if bt == None:
        login_delay = None
    else:
        login_delay = int(bt)

    bt = cfgp.get(f"TC", "linux_boot_timeout", fallback=None)
    if bt == None:
        boot_timeout = None
    else:
        boot_timeout = int(bt)

    def get_channel(self, ub: board.UBootShell)-> channel.Channel:
        """
        old bootcommands hardcoded... we should get rid of it
        only for backwardcompatibility
        """
        if "rescuetftp" in tbot.flags:
            ch = ub.boot("run", "rescuetftp")
        elif "rescue" in tbot.flags:
            ch = ub.boot("run", "rescue")
        elif "rescueuuu" in tbot.flags:
            with tbot.ctx() as cx:
                lab = cx.request(tbot.role.LabHost)
                up = lab.toolsdir()._local_str() + "/mfgtools/uuu/uuu"
                bd = lab.tftp_dir()._local_str()
                # get U-Boot into fastboot mode
                cmd = cfggeneric.fb_cmd
                cmd = cmd.strip('"')
                ub.ch.sendline(cmd)
                # load images and boot
                cmd = f"{bd}/{cfggeneric.rescueimage}"
                cmd = cmd.strip('"')
                lab.exec0(
                    linux.Raw(
                        f"sudo {up} FB: download -f {cmd}"
                    )
                )
                cmd = f"{cfggeneric.fb_res_setup}"
                cmd = cmd.strip('"')
                lab.exec0(linux.Raw(f"sudo {up} FB: ucmd {cmd}"))
                cmd = f"{cfggeneric.fb_res_boot}"
                cmd = cmd.strip('"')
                lab.exec0(linux.Raw(f"sudo {up} FB: acmd {cmd}"))
            ch = ub.boot("")
        elif "tftpfit" in tbot.flags:
            ch = ub.boot("run", "tftp_mmc")
        elif "sdcard" in tbot.flags:
            ch = ub.boot("run", "boot_mmc")
        elif "emmc" in tbot.flags:
            ch = ub.boot("run", "boot_emmc")
        elif "kas" in tbot.flags:
            ch = ub.boot("run", "bootcmdkas")
        else:
            ch = ub.boot("run", "bootcmd")

        return ch

    def do_boot(self, ub: board.UBootShell) -> channel.Channel:
        ch = None
        for f in tbot.flags:
            if "bootcmd" in f:
                bootcmd = f.split(":")[1]
                ch = ub.boot("run", bootcmd)

        if ch == None:
            ch = self.get_channel(ub)

        add_death_strings(ch)
        if "panic" in tbot.flags:
            # optional add deatch string
            self._dsc = ch.with_death_string("Kernel panic")
            self._dsc.__enter__()

        return ch

    @property
    def workdir(self) -> "linux.Path[GenericLinux]":
        return linux.Workdir.static(self, "/run/tbot-testdata")

    def tmpdir(self) -> "linux.path.Path[GenericLinux]":
        """
        returns tbot tmpdir for this lab
        """
        return linux.Workdir.static(self, f"/tmp")

    def init(self) -> None:
        # Disable all clutter on the console
        self.exec("sysctl", "kernel.printk=1 1 1 1")
        if "linux_no_cmd_after_login" in tbot.flags:
            return
        if "noboardethinit" not in tbot.flags:
            ethdevices = cfglab.ethdevices[ini.generic_get_boardname()]
            for dev in ethdevices:
                ethcfg = cfglab.ethdevices[ini.generic_get_boardname()][dev]
                # try with ip
                ret, out = self.exec("ip", "--help")
                if "useifconfig" in tbot.flags:
                        ret = 0

                if ret == 255:
                    # Yes, ip --help return 255 !?!?!?!?!
                    self.exec0(
                        "ip",
                        "link",
                        "set",
                        dev,
                        "down",
                    )
                    self.exec0(
                        "ip",
                        "addr",
                        "add",
                        f'{ethcfg["ipaddr"]}/{ethcfg["netmask"]}',
                        "dev",
                        dev,
                    )
                    self.exec0(
                        "ip",
                        "link",
                        "set",
                        dev,
                        "up",
                    )
                else:
                    # try with ifconfig
                    self.exec0(
                        "ifconfig",
                        dev,
                        "down",
                        ethcfg["ipaddr"],
                        "netmask",
                        ethcfg["netmask"],
                        "up",
                    )

            lx_init_timeout = eval(self.cfgp.get("TC", "linux_init_timeout", fallback="None"))
            if lx_init_timeout != "None":
                time.sleep(float(lx_init_timeout))

        lx_init = eval(self.cfgp.get("TC", "linux_init", fallback="[]"))
        for cmd in lx_init:
            try:
                mode = cmd["mode"]
            except:
                mode = "exec0"

            if mode == "exec0":
                self.exec0(linux.Raw(cmd["cmd"]))
            else:
                self.exec(linux.Raw(cmd["cmd"]))

class GenericLinuxBootwithoutUBootwithoutLogin(board.Connector, BOARD_LINUX_SHELL):
    """
    removed init function as we have an already running board, so we
    do not want to execute any init tasks.
    """
    name = f"{ini.generic_get_boardname()}-linux"

    cfgp = cfg.config_parser
    username = cfgp.get(f"TC", "linux_user", fallback="root")
    pwd = None

    @property
    def workdir(self) -> "linux.Path[GenericLinux]":
        return linux.Workdir.static(self, "/run/tbot-testdata")

    def tmpdir(self) -> "linux.path.Path[GenericLinux]":
        """
        returns tbot tmpdir for this lab
        """
        return linux.Workdir.static(self, f"/tmp")


class GenericLinuxBootwithoutUBoot(board.Connector, board.LinuxBootLogin, BOARD_LINUX_SHELL):
    name = f"{ini.generic_get_boardname()}-linux"

    cfgp = cfg.config_parser
    username = cfgp.get(f"TC", "linux_user", fallback="root")
    pwd = cfgp.get(f"TC", "linux_password", fallback="None")
    if pwd == "None":
            password = None
    else:
            password = pwd

    bt = cfgp.get(f"TC", "linux_login_delay", fallback=None)
    if bt == None:
        login_delay = None
    else:
        login_delay = int(bt)

    bt = cfgp.get(f"TC", "linux_boot_timeout", fallback=None)
    if bt == None:
        boot_timeout = None
    else:
        boot_timeout = int(bt)


    @property
    def workdir(self) -> "linux.Path[GenericLinux]":
        return linux.Workdir.static(self, "/run/tbot-testdata")

    def tmpdir(self) -> "linux.path.Path[GenericLinux]":
        """
        returns tbot tmpdir for this lab
        """
        return linux.Workdir.static(self, f"/tmp")

    def init(self) -> None:
        add_death_strings(self.ch)
        # Disable all clutter on the console
        self.exec("sysctl", "kernel.printk=1 1 1 1")
        if "noboardethinit" in tbot.flags:
            return

        ethdevices = cfglab.ethdevices[ini.generic_get_boardname()]
        for dev in ethdevices:
            ethcfg = cfglab.ethdevices[ini.generic_get_boardname()][dev]
            self.exec0(
                "ifconfig",
                dev,
                "down",
                ethcfg["ipaddr"],
                "netmask",
                ethcfg["netmask"],
                "up",
            )


class GenericLinuxAlwaysOn(board.Connector, BOARD_LINUX_SHELL):
    name = f"{ini.generic_get_boardname()}-linux-on"

    def init(self) -> None:
        # Disable all clutter on the console
        # self.exec0("sysctl", "kernel.printk=1 1 1 1")
        pass

    @property
    def workdir(self) -> "linux.Path[GenericLinuxAlwaysOn]":
        return linux.Workdir.static(self, "/run/tbot-testdata")

    def tmpdir(self) -> "linux.path.Path[GenericLinux]":
        """
        returns tbot tmpdir for this lab
        """
        return linux.Workdir.static(self, f"/tmp")


GenericLinux = GenericLinuxBoot
if "always-on" in tbot.flags:
    GenericBoard = lab.boardExtPower
    GenericLinux = GenericLinuxAlwaysOn  # noqa: F811 type: ignore
elif "do_power" in tbot.flags:
    GenericBoard = lab.boardControlFull
else:
    GenericBoard = lab.boardExtPower  # type: ignore

if "nouboot" in tbot.flags:
    if "ssh" in tbot.flags:
        GenericLinux = GenericLinuxBootwithoutUBootwithoutLogin
    else:
        GenericLinux = GenericLinuxBootwithoutUBoot

class GenericSSH(connector.SSHConnector, linux.Ash):
    hostname: str = None  # type: ignore
    username = "root"
    ignore_hostkey = True

    def __init__(self, lh: linux.Lab, lnx: linux.LinuxShell) -> None:
        # Find out IP address
        output = lnx.exec0("ip", "route", "get", "1")
        if "no-bootfit" not in tbot.flags:
            match = re.match(
                r"1.0.0.0 via \d+.\d+.\d+.\d+ dev \S+ src (?P<ipaddr>\d+.\d+.\d+.\d+)",  # noqa: E501
                output,
            )
        else:
            match = re.match(
                r"1.0.0.0 via \d+.\d+.\d+.\d+ dev \S+  src (?P<ipaddr>\d+.\d+.\d+.\d+)",  # noqa: E501
                output,
            )
        assert match is not None, f"invalid output from 'ip route' {output}"
        self.hostname = match.group("ipaddr")

        super().__init__(lh)

    @property
    def workdir(self) -> "linux.Path[GenericSSH]":
        return linux.Workdir.static(self, "/run/tbot-testdata")

    def tmpdir(self) -> "linux.path.Path[GenericSSH]":
        """
        returns tbot tmpdir for this lab
        """
        return linux.Workdir.static(self, f"/tmp")


def register_machines(ctx):
    ctx.register(GenericBoard, tbot.role.Board)
    ctx.register(GenericUBoot, tbot.role.BoardUBoot)
    ctx.register(GenericLinux, tbot.role.BoardLinux)


FLAGS = {
    "do_power": "tbot controlls power on/off of the board",
    "always-on": "board is already on, log into linux",
    "rescue": "boot rescue mode",
    "rescuetftp": "boot rescue mode with rescue image from tftp",
    "rescueuuu": "load bootloader with uuu tool and boot into rescue image loaded with fastboot",
    "tftpfit": "load fitimage from tftp and boot with rootfs on ubi",
    "ignore_loglevel": "add ignore_loglevel to kernel cmdline (!! may break tbot !!)",
    "sdcard": "boot linux from sd card",
    "emmc": "boot linux from emmc",
    "panic": "add death string for kernel panic",
    "nouboot" : "boot into linux without uboot interaction",
    "set-ethconfig" : "set ethernet config in u-boot",
    "nobootcon": "silent bootlogs on console",
    "bootcmd" : "run bootcommand command in U-Boot shell format: bootcmd:<command>",
    "useifconfig" : "use oldstyle ifconfig instead of ip",
}
