import ast
import os
import typing
import tbot
from tbot.machine import connector, linux, board
import tbottest.initconfig as ini
from tbot_contrib.gpio import Gpio
from tbottest.connector import KermitConnector
from tbottest.connector import PicocomConnector
from tbottest.connector import ScriptConnector
from tbottest.connector import TelnetConnector
from tbottest.bdi2000 import BDI2000
from tbottest import builders
from tbottest import powercontrol
from tbottest import machineinit
from tbottest.cmdversions import CmdVersionsMixin
from tbottest.common.boardlocking import lab_get_lock
from tbottest.common.labinit import lab_init_once
from tbottest.common.labinit import labinit_from_config
from tbottest.dynamicimport import get_boardcallback_import
from tbottest.dynamicimport import get_boardmodule_import

import tbottest.initconfighelper as inithelper

cfgt = ini.IniTBotConfig()

_INIT_CACHE: typing.Dict[str, bool] = {}

LABSECTIONNAME = inithelper.get_lab_sectionname()

if cfgt.shelltype == "bash":
    LAB_LINUX_SHELL = linux.Bash
else:
    LAB_LINUX_SHELL = linux.Ash


class boardPicocomConnector(PicocomConnector):
    bn = ini.generic_get_boardname()
    cfg = f"PICOCOM_{bn}"
    if cfgt.has_section(cfg):
        baudrate = cfgt.get_section_config(cfg, "baudrate")
        device = cfgt.get_section_config(cfg, "device")
        delay = int(cfgt.get_section_config(cfg, "delay"))
        if "True" in cfgt.get_section_config(cfg, "noreset", ""):
            noreset = True
        _tmp = cfgt.get_section_config(cfg, "slow_send_delay", None)
        if _tmp is not None:
            slow_send_delay = float(_tmp)
        _tmp = cfgt.get_section_config(cfg, "slow_send_chunksize", None)
        if _tmp is not None:
            slow_send_chunksize = int(_tmp)


class boardScriptConnector(ScriptConnector):
    bn = ini.generic_get_boardname()
    cfg = f"SCRIPTCOM_{bn}"
    if cfgt.has_section(cfg):
        scriptname = cfgt.get_section_config(cfg, "scriptname")
        exitstring = cfgt.get_section_config(cfg, "exitstring")
        boardname = bn


class boardKermitConnector(KermitConnector):
    bn = ini.generic_get_boardname()
    cfg = f"KERMIT_{bn}"
    if cfgt.has_section(cfg):
        kermit_cfg_file = cfgt.get_section_config(cfg, "cfgfile")
        kermit_delay = int(cfgt.get_section_config(cfg, "delay"))
        name = ini.generic_get_boardname()
        try:
            kermit_options = ast.literal_eval(
                cfgt.get_section_config(cfg, "kermit_options")
            )
        except Exception:
            pass


class boardTelnetConnector(TelnetConnector):
    bn = ini.generic_get_boardname()
    cfg = f"TELNET_{bn}"
    if cfgt.has_section(cfg):
        telnet_port = int(cfgt.get_section_config(cfg, "port"))
        _tmp = cfgt.get_section_config(cfg, "host", None)
        if _tmp is not None:
            telnet_host = _tmp
        try:
            telnet_delay = int(cfgt.get_section_config(cfg, "delay"))
        except Exception:
            pass


class boardSSHConnector(connector.SSHConnector):

    cfgl = ini.IniConfig()
    tmpdir = cfgl.get_config("tmpdir", "/tmp")

    ign_hostkey = cfgl.get_config_bool("ignore_hostkey", True)
    if ign_hostkey:
        ignore_hostkey = True

    username = cfgl.get_config("linux_user", "root")
    # hostname for ssh machine to board
    try:
        board_detect_lx_ethernet_interface = getattr(
            get_boardmodule_import(), "board_detect_lx_ethernet_interface"
        )
        IP_BOARD_SSH_INTERFACE = board_detect_lx_ethernet_interface()
        tbot.log.message(
            tbot.log.c(f"Use {IP_BOARD_SSH_INTERFACE} interface for ssh").yellow
        )
    except Exception:
        IP_BOARD_SSH_INTERFACE = "eth0"

    try:
        ssh_ip_section = f"IPSETUP_{ini.generic_get_boardname()}_{IP_BOARD_SSH_INTERFACE}"
        IP_BOARD = cfgt.get_section_config(ssh_ip_section, "ipaddr")
        hostname = IP_BOARD
    except Exception:
        RuntimeError(
            f"Please set ipaddr for ssh machine. Expect section {ssh_ip_section} with key ipaddr"
        )

    @property
    def authenticator(self) -> linux.auth.Authenticator:
        cfgb = ini.IniConfig()
        ssh_keyfile = cfgb.get_config("ssh_keyfile", "None")
        if ssh_keyfile:
            return linux.auth.PrivateKeyAuthenticator(ssh_keyfile)

        ssh_password = cfgb.get_config("ssh_password", "None")
        if ssh_password:
            return linux.auth.PasswordAuthenticator(ssh_password)

        # default, hopefully ssh config has all needed settings
        return linux.auth.NoneAuthenticator()


class boardGpioControl(powercontrol.GpiopmControl):
    def power_check(self) -> bool:
        if "poweroffonstart" in tbot.flags:
            self.poweroff()

        return True

    bn = ini.generic_get_boardname()
    cfg = f"GPIOPMCTRL_{bn}"
    if cfgt.has_section(cfg):
        gpiopmctl_pin = cfgt.get_section_config(cfg, "gpiopmctl_pin")
        gpiopmctl_state = cfgt.get_section_config(cfg, "gpiopmctl_state")


class boardPowerShellControl(powercontrol.PowerShellScriptControl):
    def power_check(self) -> bool:
        if "poweroffonstart" in tbot.flags:
            self.poweroff()

        return True

    bn = ini.generic_get_boardname()
    cfg = f"POWERSHELLSCRIPT_{bn}"
    if cfgt.has_section(cfg):
        shell_script = ast.literal_eval(cfgt.get_section_config(cfg, "script"))


class boardShellyControl(powercontrol.ShellyControl):
    def power_check(self) -> bool:
        if "poweroffonstart" in tbot.flags:
            self.poweroff()

        return True

    bn = ini.generic_get_boardname()
    cfg = f"SHELLY_{bn}"
    if cfgt.has_section(cfg):
        shelly_device = cfgt.get_section_config(cfg, "device")
        shelly_id = cfgt.get_section_config(cfg, "id", "0")
        shelly_command = cfgt.get_section_config(cfg, "command", None)
        shelly_timeout = cfgt.get_section_config(cfg, "timeout", None)
        shelly_install = cfgt.get_section_config_bool(cfg, "install", True)


class boardSisControl(powercontrol.SispmControl):
    def power_check(self) -> bool:
        if "poweroffonstart" in tbot.flags:
            self.poweroff()

        return True

    bn = ini.generic_get_boardname()
    cfg = f"SISPMCTRL_{bn}"
    if cfgt.has_section(cfg):
        sispmctl_device = cfgt.get_section_config(cfg, "device")
        sispmctl_port = cfgt.get_section_config(cfg, "port")


class boardTboxControl(powercontrol.TboxCtrlControl):
    def power_check(self) -> bool:
        if "poweroffonstart" in tbot.flags:
            self.poweroff()

        return True

    bn = ini.generic_get_boardname()
    cfg = f"TBOX_{bn}"
    if cfgt.has_section(cfg):
        tbox_powerpin = cfgt.get_section_config(cfg, "powerpin")

        _vid = cfgt.get_section_config(cfg, "vid", None)
        _pid = cfgt.get_section_config(cfg, "pid", None)
        tbox_vid = int(_vid, 0) if _vid else None
        tbox_pid = int(_pid, 0) if _pid else None


class boardTboxHwdaemonControl(powercontrol.TboxHwdaemonControl):
    def power_check(self) -> bool:
        if "poweroffonstart" in tbot.flags:
            self.poweroff()

        return True

    bn = ini.generic_get_boardname()
    cfg = f"TBOX_HWDAEMON_{bn}"
    if cfgt.has_section(cfg):
        hwdaemon_boardname = cfgt.get_section_config(cfg, "boardname")
        _configfile = cfgt.get_section_config(cfg, "configfile", None)
        if _configfile:
            hwdaemon_configfile = _configfile


class boardTMControl(powercontrol.TM021Control):
    def power_check(self) -> bool:
        if "poweroffonstart" in tbot.flags:
            self.poweroff()

        return True

    bn = ini.generic_get_boardname()
    cfg = f"TM021_{bn}"
    if cfgt.has_section(cfg):
        tm021_device = cfgt.get_section_config(cfg, "device")
        tm021_baudrate = cfgt.get_section_config(cfg, "baudrate")
        tm021_timeout = cfgt.get_section_config(cfg, "timeout")
        tm021_address = cfgt.get_section_config(cfg, "address")
        tm021_port = cfgt.get_section_config(cfg, "port")
        tm021_debug = cfgt.get_section_config(cfg, "debug")


class boardTFControl(powercontrol.TinkerforgeControl):
    bn = ini.generic_get_boardname()
    cfg = f"TF_{bn}"
    if cfgt.has_section(cfg):
        name = cfg.split("_")[1]
        uid = cfgt.get_section_config(cfg, "uid")
        channel = cfgt.get_section_config(cfg, "channel")


if "tinkerforge" in tbot.flags:
    BOARDCTL = boardTFControl
elif "gpiopower" in tbot.flags:
    BOARDCTL = boardGpioControl
elif "powershellscript" in tbot.flags:
    BOARDCTL = boardPowerShellControl
else:
    # try to autodetect from tbot.ini file
    if cfgt.sispmctrl:
        BOARDCTL = boardSisControl
    elif cfgt.powershellscript:
        BOARDCTL = boardPowerShellControl
    elif cfgt.gpiopowerctrl:
        BOARDCTL = boardGpioControl
    elif cfgt.tinkerforce:
        BOARDCTL = boardTFControl
    elif cfgt.tm021:
        BOARDCTL = boardTMControl
    elif cfgt.tbox:
        BOARDCTL = boardTboxControl
    elif cfgt.tboxhwdaemon:
        BOARDCTL = boardTboxHwdaemonControl
    elif cfgt.shelly:
        BOARDCTL = boardShellyControl
    else:
        bn = ini.generic_get_boardname()
        raise RuntimeError(f"please configure powerctrl for board {bn}")


# if we want to download bootloader with uuu tool
# after powering on the board, we must load the bootloader
# with the uuu tool onto the board
class boardControlUUU(BOARDCTL, machineinit.UUULoad):
    def get_uuu_tool(self):
        return self.host.toolsdir()

    def uuu_loader_steps(self):
        lbd = self.host.tftp_dir()._local_str()
        ucfg = cfgt.uuucfg[ini.generic_get_boardname()]
        cmds = []
        for n in ucfg:
            new = n.replace("LBD", lbd)
            cmds.append(linux.Raw(new))

        return cmds


class boardControlXmodem(BOARDCTL, machineinit.XMODEMLoad):
    def xmodem_loader_device(self):
        return cfgt.xmodemdevice[ini.generic_get_boardname()]

    def xmodem_loader_steps(self):
        lbd = self.host.tftp_dir()._local_str()
        xcfg = cfgt.xmodemcfg[ini.generic_get_boardname()]
        xdev = self.xmodem_loader_device()
        cmds = [s.replace("TFTPDIR", lbd) for s in xcfg]
        cmds = [s.replace("SERDEV", xdev) for s in cmds]
        return cmds


class boardControlDFUUTIL(BOARDCTL, machineinit.DFUUTIL):
    def dfuutil_loader_steps(self):
        tftpd = self.host.tftp_dir()._local_str()
        cfg = cfgt.dfuutilcfg[ini.generic_get_boardname()]
        for c in cfg:
            c["a"] = c["a"].replace("LBD", tftpd)
            c["D"] = c["D"].replace("LBD", tftpd)

        return cfg


# if we want to download bootloader with Lauterbach TRACE32
# after powering on the board, we must load the bootloader
# with the trace32 tool onto the board
class boardControlLauterbach(BOARDCTL, machineinit.LauterbachLoad):
    def get_host(self):
        if "lauterbachusesshmachine" in tbot.flags:
            with tbot.ctx() as cx:
                lab = cx.request(tbot.role.LabHost)

                if lab.has_sshmachine():
                    with lab.sshmachine() as lnxssh:
                        # lnxssh.exec0("uname", "-a")
                        # ret, log = lnxssh.exec("ps", "afx", linux.Raw("|"), "grep", "dummy-1920x1080.conf", linux.Raw("|"), "grep", "-v", "grep")
                        # if ret != 0:
                        #    lnxssh.exec0("sudo", "X", "-config", "/home/hs/data/Entwicklung/XXX/dummy-1920x1080.conf", ":99", linux.Raw("&"))
                        # lnxssh.exec0("export", "DISPLAY=:99")

                        return lnxssh

        return self.host

    def get_trace32_verbose(self):
        cfg = cfgt.lauterbachcfg[ini.generic_get_boardname()]
        return cfg["verbose"]

    def get_trace32_install_path(self):
        cfg = cfgt.lauterbachcfg[ini.generic_get_boardname()]
        return cfg["install_path"]

    def get_trace32_cmd(self):
        cfg = cfgt.lauterbachcfg[ini.generic_get_boardname()]
        return cfg["cmd"]

    def get_trace32_config(self):
        cfg = cfgt.lauterbachcfg[ini.generic_get_boardname()]
        return cfg["config"]

    def get_trace32_script(self):
        cfg = cfgt.lauterbachcfg[ini.generic_get_boardname()]
        return cfg["script"]


# if we want to download bootloader with Segger JLink
# after powering on the board, we must load the bootloader
# with the JLinkExe tool onto the board
class boardControlSegger(BOARDCTL, machineinit.SeggerLoad):
    def get_host(self):
        return self.host

    def get_segger_cmds(self):
        cfg = cfgt.seggercfg[ini.generic_get_boardname()]
        return cfg["cmds"]


# if the board's BDI2000 has commands to run after power on (e.g. "reset
# run" while the BDI holds the CPU in reset), run them on the BDI2000
class boardControlBDI2000(BOARDCTL, machineinit.BDI2000Cmds):
    def get_bdi2000_cmds(self):
        return _BDI2000_POWERON_CMDS

    def get_bdi2000_wait_state(self):
        return cfgt.bdi2000cfg[ini.generic_get_boardname()]["poweron_wait_state"]

    def get_bdi2000_timeout(self):
        return cfgt.bdi2000cfg[ini.generic_get_boardname()]["poweron_timeout"]


class GenericBDI2000(TelnetConnector, BDI2000):
    name = "bdi2000"
    telnet_port = 23

    @property
    def telnet_host(self) -> str:
        return cfgt.bdi2000cfg[ini.generic_get_boardname()]["ip"]


_BDI2000CFG = cfgt.bdi2000cfg.get(ini.generic_get_boardname(), {})
# selected with the flag poweron_cmds:<name>, empty for poweron_cmds:None
_BDI2000_POWERON_CMDS = ini.bdi2000_poweron_cmds(_BDI2000CFG.get("poweron_cmds", []))

if "uuuloader" in tbot.flags:
    BOARDCTRL = boardControlUUU
elif "dfuutilloader" in tbot.flags:
    BOARDCTRL = boardControlDFUUTIL
elif "lauterbachloader" in tbot.flags:
    BOARDCTRL = boardControlLauterbach
elif "seggerloader" in tbot.flags:
    BOARDCTRL = boardControlSegger
elif "xmodemloader" in tbot.flags:
    BOARDCTRL = boardControlXmodem
elif _BDI2000_POWERON_CMDS:
    BOARDCTRL = boardControlBDI2000
else:
    BOARDCTRL = BOARDCTL

if "ssh" in tbot.flags:
    BOARDCON = boardSSHConnector
elif "picocom" in tbot.flags:
    BOARDCON = boardPicocomConnector
elif "scriptcom" in tbot.flags:
    BOARDCON = boardScriptConnector
elif "telnet" in tbot.flags:
    BOARDCON = boardTelnetConnector
else:
    # try to autodetect setup (config from tbot.ini file)
    if cfgt.kermit:
        BOARDCON = boardKermitConnector
    elif cfgt.picocom:
        BOARDCON = boardPicocomConnector
    elif cfgt.scriptcom:
        BOARDCON = boardScriptConnector
    elif cfgt.telnet:
        BOARDCON = boardTelnetConnector
    else:
        raise RuntimeError("Please setup console connector")


class boardControlFull(BOARDCON, BOARDCTRL, board.Board):
    pass


class boardExtPower(BOARDCON, board.Board):
    pass


if "local" in tbot.flags:
    CON = connector.SubprocessConnector
else:
    CON = connector.SSHConnector

BH = typing.TypeVar("BH", bound=linux.Builder)


class GenericLab(CmdVersionsMixin, CON, LAB_LINUX_SHELL, linux.Lab, linux.Builder):
    sectionname = LABSECTIONNAME
    # preset for cmd_get_version(), see tbottest.cmdversions
    cmd_versions_config = cfgt.get_lab_config("cmd_versions", None)
    tmpdir_exists = False
    nfsbasedir = True
    nfsboardbasedir = True
    name = cfgt.get_lab_config("labname")
    hostname = cfgt.get_lab_config("hostname")
    username = cfgt.get_lab_config("username")
    tftproot = cfgt.get_lab_config("tftproot")
    port = cfgt.get_lab_config("port", 22)
    nfs_base_path = cfgt.get_lab_config("nfs_base_path")
    enablelocking = cfgt.get_lab_config("uselocking", "no").lower()

    bootmodecfg = cfgt.bootmodecfg
    ubcfg = cfgt.ubcfg
    ethdevices = cfgt.ethdevices
    uuucfg = cfgt.uuucfg
    lauterbachcfg = cfgt.lauterbachcfg
    seggercfg = cfgt.seggercfg

    @property
    def ssh_config(self) -> typing.List[str]:
        """
        if ProxyJump does not work, execute this command from hand
        on the lab PC with BatchMode=no" -> answer allwith "yes"
        If again password question pops up, copy id_rsa.pub from
        lab PC to authorized_keys on build PC
        """
        args = []
        if "outside" in tbot.flags:
            tmp = cfgt.get_lab_config("proxyjump", None)
            if tmp is not None:
                args.append(f"ProxyJump={tmp}")

        return args

    @property
    def authenticator(self) -> linux.auth.Authenticator:
        tmp = cfgt.get_lab_config("sshkeyfile", None)
        if tmp is not None:
            return linux.auth.PrivateKeyAuthenticator(tmp)

        password = cfgt.get_lab_config("password", None)
        if password is not None:
            return linux.auth.PasswordAuthenticator(password)
        else:
            raise RuntimeError(
                f"you need to setup Authenticator for {self.name}. Set 'sshkeyfile' or 'password' in section [{LABSECTIONNAME}] in tbot.ini"
            )

    def tftp_dir(self) -> "linux.path.Path[GenericLab]":
        tmp = linux.Path(self, self.tftp_root_path() / self.tftp_dir_board())
        # check if path exists, if not create it
        self.exec0("mkdir", "-p", tmp)
        return tmp

    def tftp_root_path(self) -> "linux.Path[GenericLab]":
        """
        returns root tftp path
        """
        return linux.Path(self, self.tftproot)

    def tftp_dir_board(self) -> "linux.Path[GenericLab]":
        """
        returns tftp path for u-boot tftp command
        """
        tmp = cfgt.get_lab_config("tftpsubdir")

        return linux.Path(self, tmp)

    def workdir(self) -> "linux.path.Path[GenericLab]":
        """
        returns tbot workdir for this lab
        """
        tmp = cfgt.get_lab_config("workdir")
        return linux.Workdir.static(self, tmp)

    def testdir(self) -> "linux.path.Path[GenericLab]":
        """
        returns the directory for what testcases install or build on this
        lab, key testdir in the lab section of tbot.ini, default
        <workdir>/tbottests
        """
        tmp = cfgt.get_lab_config("testdir", None)
        if not tmp:
            tmp = self.workdir()._local_str() + "/tbottests"
        return linux.Workdir.static(self, tmp)

    def tmpdir(self) -> "linux.path.Path[GenericLab]":
        """
        returns tbot tmpdir for this lab
        """
        tmp = cfgt.get_lab_config("tmpdir")
        if self.tmpdir_exists is False:
            ret, log = self.exec("ls", tmp)
            if ret != 0:
                self.exec0("mkdir", "-p", tmp)
                self.tmpdir_exists = True

        return linux.Workdir.static(self, tmp)

    def tmpmntdir(self, name: str) -> "linux.path.Path[GenericLab]":
        """
        returns tbot tmpdir for mounting stuff on this lab
        """
        tmp = self.tmpdir()
        return linux.Workdir.static(self, tmp / f"mnt{name}")

    def nfsbasedir(self) -> "linux.path.Path[GenericLab]":
        """
        returns nfs base directory, configured in section [LABHOST]
        in ```tbot.ini```, key value ```nfs_base_path```
        """
        tmp = linux.Path(self, self.nfs_base_path)
        if self.nfsbasedir is False:
            ret, log = self.exec("ls", tmp)
            if ret != 0:
                self.exec0("mkdir", "-p", tmp)
                self.nfsbasedir_exists = True

        return linux.Workdir.static(self, tmp)

    def nfsboardbasedir(self) -> "linux.path.Path[GenericLab]":
        """
        returns nfs base directory for the specific board,
        configured in section [default] in ```BOARDNAME.ini```,
        key value ```nfs_path```
        """
        # we need board config here, but we cannot import
        # this global
        from tbottest.boardgeneric import cfggeneric

        cfg = cfggeneric
        tmp = cfg.get_default_config("nfs_path", None)
        if tmp is None:
            raise RuntimeError("nfs_path missing in section [default] of the board ini")
        if self.nfsboardbasedir is False:
            ret, log = self.exec("ls", tmp)
            if ret != 0:
                self.exec0("mkdir", "-p", tmp)
                self.nfsboardbasedir = True

        return linux.Workdir.static(self, tmp)

    def toolsdir(self) -> "linux.path.Path[GenericLab]":
        """
        returns directory where tbot finds tools
        """
        tmp = cfgt.get_lab_config("toolsdir")
        return linux.Path(self, tmp)

    def yocto_result_dir(self) -> "linux.Path[GenericLab]":
        """
        returns path to directory where tbot finds yocto build results
        """
        return self.tftp_dir()

    @property
    def toolchains(self) -> typing.Dict[str, linux.build.Toolchain]:
        return {
            "bootlin-armv5-eabi": linux.build.EnvSetBootlinToolchain(
                arch="armv5-eabi",
                libc="glibc",
                typ="stable",
                date="2018.11-1",
            ),
            "linaro-gnueabi": linux.build.EnvSetLinaroToolchain(
                host_arch="x86_64",
                arch="arm-linux-gnueabi",
                date="2019.12",
                gcc_vers="7.5",
                gcc_subvers="0",
            ),
        }

    def lab_set_sd_mux_mode(self, mode: str):
        """
        set sd mux mode to lab or dut
        """
        if mode == "lab":
            md = "--ts"
        elif mode == "dut":
            md = "--dut"
        else:
            raise RuntimeError("only mode 'dut' or 'lab' allowed for mode not {mode}")

        try:
            sdwireserial = cfgt.get_section_config("SDWIRE", "serial")
            from tbottest.tc.common import lnx_sudo

            self.exec0(
                *lnx_sudo(self),
                "sd-mux-ctrl",
                f"--device-serial={sdwireserial}",
                md,
            )
        except Exception:
            tbot.log.message(tbot.log.c("no sd wire on this labhost").yellow)
            pass

    def set_bootmode(self, wantbootmode: str = None) -> bool:
        """
        set the bootmode defined in config file section [BOOTMODE_<boardname>]

        example config for gpio setup:

        .. code-block:: ini

            [BOOTMODE_testboard]
            modes = [{"name":"bootmode:uart0", "gpios":"26:1 19:0"}, {"name":"bootmode:spinor", "gpios":"26:0 19:0"} ]

        .. code-block:: bash

            -f bootmode:uart0
            -f bootmode:spinor

        example config for cmd setup:

        .. code-block:: ini

            [BOOTMODE_testboard]
            modes = [{"name":"bootmode:dfu", "cmd":"stty -F /dev/ttyACM0 9600;echo 'on' > /dev/ttyACM0"}, {"name":"bootmode:emmc", "cmd":"stty -F /dev/ttyACM0 9600;echo 'off' > /dev/ttyACM0"} ]

        .. code-block:: bash

            -f bootmode:dfu
            -f bootmode:emmc


        example config for sd mux:

        .. code-block:: ini

            [BOOTMODE_testboard]
            modes = [{"name":"bootmode:sd", "sdwire":"dut"}, {"name":"bootmode:emmc", "sdwire":"lab"} ]

        .. code-block:: bash

            -f bootmode:sd
            -f bootmode:emmc

        example config for calling function in tbotconfig/labcallbacks.py:

        .. code-block:: ini

            [BOOTMODE_testboard]
            modes = [{"name":"bootmode:usb", "func":"board_setbootmode_usb"}, {"name":"bootmode:emmc", "func":"board_setbootmode_emmc"} ]

        .. code-block:: bash

            -f bootmode:usb
            -f bootmode:emmc

        .. warning::

            This is a hack !

            You need to add the new file tbotconfig/labcallbacks.py and
            implement there the files you define in "modes"

            Only use it, for fast testing, then implement it in a class!

        Currently there is only one argument passed:

        Example code

        .. code-block:: python

            def board_setbootmode_usb(
                lab: linux.LinuxShell = None,
            ) -> None:  # noqa: D107
                # call commands on lab with
                # lab.exec0("....")
                return True

        :param wantbootmode: str, bootmode string, use this, when you call the function from within python function
        """
        try:
            bootmodes = self.bootmodecfg[ini.generic_get_boardname()]
        except Exception:
            return True

        bms = None
        bmtype = None
        if wantbootmode:
            for bm in bootmodes:
                if bm["name"] in wantbootmode:
                    bms = bm
                    bmtype = "function"

        if bms == None:
            for bm in bootmodes:
                if bm["name"] in tbot.flags:
                    bms = bm
                    bmtype = "tbot.flag"

        if bms != None:
            tbot.log.message(
                tbot.log.c(f"set bootmode {bms['name']} from {bmtype}").yellow
            )
            try:
                gpios = bms["gpios"]
                for s in gpios.split(" "):
                    gpionr = s.split(":")[0]
                    state = s.split(":")[1]
                    gpio = Gpio(self, gpionr)
                    gpio.set_direction("out")
                    if int(state) == 0:
                        gpio.set_value(False)
                    else:
                        gpio.set_value(True)
                return True
            except Exception:
                pass

            try:
                self.lab_set_sd_mux_mode(bms["sdwire"])
                return True
            except Exception:
                pass

            try:
                cmd = bms["cmd"]
                return self.exec0(linux.Raw(cmd))
            except Exception:
                pass

            try:
                funcname = bms["func"]
                func = getattr(get_boardcallback_import(), funcname)
                ret = func(self)
                return ret
            except Exception:
                pass

            tbot.log.message(tbot.log.c(f"set bootmode {bms['name']} failed").red)
            raise RuntimeError(f"Exit until callbacks work")

        return False

    def check_locking(self) -> None:
        if self.enablelocking == "yes":
            lab_get_lock(self)

    def init(self) -> None:
        self.check_locking()

        # check if nfs server is running, if not start it
        # utils.ensure_sd_unit(self, ["nfs-server.service", "tftp.socket"])
        # check if we have eth0 connection, link and carrier
        # do not know, why pi always has no-carrier !!
        self.set_bootmode()

        if "LABINIT" not in _INIT_CACHE:
            _INIT_CACHE["LABINIT"] = True

            bn = ini.generic_get_boardname()
            ethinit = "noethinit" not in tbot.flags
            lab_init_once(
                self,
                labinit_from_config(cfgt.get_lab_config("labinit", None)),
                bn,
                self.ethdevices[bn] if ethinit else {},
                ethinit=ethinit,
            )

    def has_sshmachine(self) -> bool:
        return bool(cfgt.find_sections("SSHMACHINE"))

    def sshmachine(self) -> linux.Bash:
        if self.has_sshmachine:
            return SSHMachine(self)

        return None


class SSHMachine(connector.SSHConnector, linux.Bash):
    try:
        name = cfgt.get_section_config("SSHMACHINE", "name")
        username = cfgt.get_section_config("SSHMACHINE", "username")
        port = cfgt.get_section_config("SSHMACHINE", "port")
        hostname = cfgt.get_section_config("SSHMACHINE", "hostname")
        wdir = cfgt.get_section_config("SSHMACHINE", "workdir")
    except Exception:
        pass

    def tftp_dir(self) -> "linux.path.Path[SSHMachine]":
        return self.workdir

    def toolsdir(self) -> "linux.path.Path[SSHMachine]":
        toolsdir = cfgt.get_section_config("SSHMACHINE", "toolsdir")
        return linux.Path(self, toolsdir)

    @property
    def workdir(self) -> "linux.Path[SSHMachine]":
        return linux.Workdir.static(self, self.wdir)

    @property
    def testdir(self) -> "linux.Path[SSHMachine]":
        """
        directory for what testcases install or build on this machine,
        key testdir in [SSHMACHINE], default <workdir>/tbottests
        """
        tmp = cfgt.get_section_config("SSHMACHINE", "testdir", None)
        if not tmp:
            tmp = self.wdir + "/tbottests"
        return linux.Workdir.static(self, tmp)

    def init(self) -> None:
        # do stuff after login
        # self.exec0("uname", "-a")
        return None


class LocalHostTest(
    connector.SubprocessConnector, linux.Bash, linux.Lab, typing.ContextManager
):
    workdir_exists = False

    def workdir(self) -> "linux.path.Path[LocalHostTest]":
        """
        returns tbot workdir on Local Host

        default is ```/tmp```

        If you want to set it to other path set Environment
        variable ```TBOTTESTWORKPATH```
        """
        try:
            tmp = os.environ["TBOTTESTWORKPATH"]
        except Exception:
            tmp = "/tmp"

        tmp = f"{tmp}/tbot"
        if self.workdir_exists is False:
            self.exec0("mkdir", "-p", tmp)
            self.workdir_exists = True

        return linux.Workdir.static(self, tmp)

    def sourcedir(self) -> "linux.path.Path[LocalHostTest]":
        """
        returns tbottest sourcedir on Local host
        (installation path of tbottest)

        default is ```.```

        If you need, you can set the path to tbottest
        through Environment variable ```TBOTTESTPATH```
        """
        try:
            tmp = os.environ["TBOTTESTPATH"]
        except Exception:
            tmp = "."

        return linux.Workdir.static(self, tmp)


def register_machines(ctx):
    ctx.register(GenericLab, tbot.role.LabHost)
    if _BDI2000CFG:
        ctx.register(GenericBDI2000, BDI2000)
    ctx.register(LocalHostTest, tbot.role.LocalHost)
    if cfgt.find_sections("BUILDHOST"):
        if any("buildername:local" in f for f in tbot.flags):
            # build on machine, on which tbot is startet!
            ctx.register(builders.genericbuilderlocal, tbot.role.BuildHost)
        else:
            ctx.register(builders.genericbuilder, tbot.role.BuildHost)


FLAGS = {
    "local": "enable if labhost and tbot host are the same (use SubprocessConnector)",
    "ssh": "use as boards console login with ssh",
    "picocom": "use piccom for accessing serial console",
    "scriptcom": "use a script for accessing serial console",
    "tinkerforge": "use tinkerforge for switching power",
    "gpiopower": "use gpio pin for switching power",
    "powershellscript": "use a shell script for switching power",
    "poweroffonstart": "always power off board on tbot start",
    "labname": "select which labhost we use",
    "cmdtimestamp": "prefix each command log line with a H:M:S timestamp",
    "lablockid": "lablockid:<yourlockid> lock id for board locking",
    "lauterbachusesshmachine": "with lauterbachloader, run TRACE32 on the SSH machine",
    "noethinit": "no ethernet setup of the lab host for the board",
    "outside": "lab host is only reachable with proxyjump",
    "telnet": "use telnet for accessing serial console",
}
