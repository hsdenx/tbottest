import typing
import tbot
from tbot.machine import connector, linux, board
import time
import tbottest.initconfig as ini
from tbot_contrib.gpio import Gpio
from tbottest.connector import KermitConnector
from tbottest.connector import PicocomConnector
from tbottest.connector import ScriptConnector
from tbottest import builders
from tbottest import powercontrol
from tbottest import machineinit
from tbottest.common.boardlocking import lab_get_lock

import tbottest.initconfighelper as inithelper

cfgt = ini.IniTBotConfig()

_INIT_CACHE: typing.Dict[str, bool] = {}

LABSECTIONNAME = inithelper.get_lab_sectionname()

LABNAME = cfgt.config_parser.get(LABSECTIONNAME, "labname")

if cfgt.shelltype == "bash":
    LAB_LINUX_SHELL = linux.Bash
else:
    LAB_LINUX_SHELL = linux.Ash

# for ssh machine
IP_BOARD_SSH_INTERFACE = "eth0"
try:
    ssh_ip_section = f"IPSETUP_{ini.generic_get_boardname()}_{IP_BOARD_SSH_INTERFACE}"
    IP_BOARD = cfgt.config_parser.get(ssh_ip_section, "ipaddr")
except:
    IP_BOARD = None


class boardPicocomConnector(PicocomConnector):
    bn = ini.generic_get_boardname()
    cfg = f"PICOCOM_{bn}"
    for s in cfgt.config_parser.sections():
        if cfg == s:
            baudrate = cfgt.config_parser.get(s, "baudrate")
            device = cfgt.config_parser.get(s, "device")
            delay = int(cfgt.config_parser.get(s, "delay"))
            try:
                tmp = cfgt.config_parser.get(s, "noreset")
                if "True" in tmp:
                    noreset = True
            except:  # noqa: E722
                pass

class boardScriptConnector(ScriptConnector):
    bn = ini.generic_get_boardname()
    cfg = f"SCRIPTCOM_{bn}"
    for s in cfgt.config_parser.sections():
        if cfg == s:
            scriptname = cfgt.config_parser.get(s, "scriptname")
            exitstring = cfgt.config_parser.get(s, "exitstring")
            boardname = bn

class boardKermitConnector(KermitConnector):
    bn = ini.generic_get_boardname()
    cfg = f"KERMIT_{bn}"
    for s in cfgt.config_parser.sections():
        if cfg == s:
            kermit_cfg_file = cfgt.config_parser.get(s, "cfgfile")
            kermit_delay = int(cfgt.config_parser.get(s, "delay"))
            name = ini.generic_get_boardname()


class boardSSHConnector(connector.SSHConnector):

    cfgl = ini.IniConfig()
    cfgp = cfgl.config_parser
    tmpdir = cfgp.get("TC", "tmpdir", fallback="/tmp")

    ign_hostkey = cfgp.getboolean("TC", "ignore_hostkey", fallback=True)
    if ign_hostkey:
        ignore_hostkey = True

    username = ini.init_get_config(cfgp, "linux_user", "root")
    if IP_BOARD is None:
        RuntimeError(
            f"Please set ipaddr for ssh machine. Expect section {ssh_ip_section} with key ipaddr"
        )

    hostname = IP_BOARD

    @property
    def authenticator(self) -> linux.auth.Authenticator:
        cfgb = ini.IniConfig()
        cfgp = cfgb.config_parser
        ssh_keyfile = ini.init_get_config(cfgp, "ssh_keyfile", "None")
        if ssh_keyfile:
            return linux.auth.PrivateKeyAuthenticator(ssh_keyfile)

        ssh_password = ini.init_get_config(cfgp, "ssh_password", "None")
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
    for s in cfgt.config_parser.sections():
        if cfg == s:
            gpiopmctl_pin = cfgt.config_parser.get(s, "gpiopmctl_pin")
            gpiopmctl_state = cfgt.config_parser.get(s, "gpiopmctl_state")


class boardPowerShellControl(powercontrol.PowerShellScriptControl):
    def power_check(self) -> bool:
        if "poweroffonstart" in tbot.flags:
            self.poweroff()

        return True

    bn = ini.generic_get_boardname()
    cfg = f"POWERSHELLSCRIPT_{bn}"
    for s in cfgt.config_parser.sections():
        if cfg == s:
            shell_script = eval(cfgt.config_parser.get(s, "script"))


class boardSisControl(powercontrol.SispmControl):
    def power_check(self) -> bool:
        if "poweroffonstart" in tbot.flags:
            self.poweroff()

        return True

    bn = ini.generic_get_boardname()
    cfg = f"SISPMCTRL_{bn}"
    for s in cfgt.config_parser.sections():
        if cfg == s:
            sispmctl_device = cfgt.config_parser.get(s, "device")
            sispmctl_port = cfgt.config_parser.get(s, "port")


class boardTFControl(powercontrol.TinkerforgeControl):
    bn = ini.generic_get_boardname()
    cfg = f"TF_{bn}"
    for s in cfgt.config_parser.sections():
        if cfg == s:
            name = s.split("_")[1]
            uid = cfgt.config_parser.get(s, "uid")
            channel = cfgt.config_parser.get(s, "channel")


if "tinkerforge" in tbot.flags:
    BOARDCTL = boardTFControl
elif "gpiopower" in tbot.flags:
    BOARDCTL = boardGpioControl
elif "powershellscript" in tbot.flags:
    BOARDCTL = boardPowerShellControl
else:
    BOARDCTL = boardSisControl


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


if "uuuloader" in tbot.flags:
    BOARDCTRL = boardControlUUU
elif "lauterbachloader" in tbot.flags:
    BOARDCTRL = boardControlLauterbach
elif "seggerloader" in tbot.flags:
    BOARDCTRL = boardControlSegger
else:
    BOARDCTRL = BOARDCTL

if "ssh" in tbot.flags:
    BOARDCON = boardSSHConnector
elif "picocom" in tbot.flags:
    BOARDCON = boardPicocomConnector
elif "scriptcom" in tbot.flags:
    BOARDCON = boardScriptConnector
else:
    # try to autodetect setup (config from tbot.ini file)
    if cfgt.kermit:
        BOARDCON = boardKermitConnector
    elif cfgt.picocom:
        BOARDCON = boardPicocomConnector
    elif cfgt.scriptcom:
        BOARDCON = boardScriptConnector
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


class GenericLab(CON, LAB_LINUX_SHELL, linux.Lab, linux.Builder):
    sectionname = LABSECTIONNAME
    tmpdir_exists = False
    nfsbasedir = True
    nfsboardbasedir = True
    name = cfgt.config_parser.get(LABSECTIONNAME, "labname")
    hostname = cfgt.config_parser.get(LABSECTIONNAME, "hostname")
    username = cfgt.config_parser.get(LABSECTIONNAME, "username")
    tftproot = cfgt.config_parser.get(LABSECTIONNAME, "tftproot")
    port = cfgt.config_parser.get(LABSECTIONNAME, "port", fallback=22)
    nfs_base_path = cfgt.config_parser.get(LABSECTIONNAME, "nfs_base_path")
    try:
        enablelocking = cfgt.config_parser.get(LABSECTIONNAME, "uselocking")
        enablelocking = enablelocking.lower()
    except:
        enablelocking = "no"

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
            try:
                tmp = cfgt.config_parser.get(LABSECTIONNAME, "proxyjump")
                args.append(f"ProxyJump={tmp}")
            except:  # noqa: E722
                pass

        return args

    @property
    def authenticator(self) -> linux.auth.Authenticator:
        try:
            tmp = cfgt.config_parser.get(LABSECTIONNAME, "sshkeyfile")
            return linux.auth.PrivateKeyAuthenticator(tmp)
        except:
            pass

        try:
            password = cfgt.config_parser.get(LABSECTIONNAME, "password")
            return linux.auth.PasswordAuthenticator(password)
        except:
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
        tmp = cfgt.config_parser.get(LABSECTIONNAME, "tftpsubdir")

        return linux.Path(self, tmp)

    def workdir(self) -> "linux.path.Path[GenericLab]":
        """
        returns tbot workdir for this lab
        """
        tmp = cfgt.config_parser.get(LABSECTIONNAME, "workdir")
        return linux.Workdir.static(self, tmp)

    def tmpdir(self) -> "linux.path.Path[GenericLab]":
        """
        returns tbot tmpdir for this lab
        """
        tmp = cfgt.config_parser.get(LABSECTIONNAME, "tmpdir")
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
        tmp = cfg.cfgp.get("default", "nfs_path")
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
        tmp = cfgt.config_parser.get(LABSECTIONNAME, "toolsdir")
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
            sdwireserial = cfgt.config_parser.get("SDWIRE", "serial")
            self.exec0(
                "sudo",
                "/usr/local/bin/sd-mux-ctrl",
                f"--device-serial={sdwireserial}",
                md,
            )
        except:  # noqa: E722
            tbot.log.message(tbot.log.c("no sd wire on this labhost").yellow)
            pass

    def set_bootmode(self) -> bool:
        """
        set the bootmode defined in config file section [BOOTMODE_<boardname>]

        example config for gpio setup:

        .. code-block:: ini

            [BOOTMODE_testboard]
            modes = [{"name":"bootmode:uart0", "gpios":"26:1 19:0"}, {"name":"bootmode:spinor", "gpios":"26:0 19:0"} ]

        .. code-block:: bash

            -f bootmode:uart0
            -f bootmode:spinor

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

        """
        try:
            bootmodes = self.bootmodecfg[ini.generic_get_boardname()]
        except:
            return True

        for bm in bootmodes:
            if bm["name"] in tbot.flags:
                tbot.log.message(tbot.log.c(f"set bootmode {bm['name']}").yellow)
                try:
                    gpios = bm["gpios"]
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
                except:
                    pass

                try:
                    self.lab_set_sd_mux_mode(bm["sdwire"])
                    return True
                except:
                    pass

                try:
                    from tbotconfig import labcallbacks

                    funcname = bm['func']
                    func = getattr(labcallbacks, funcname)
                    ret = func(self)
                    return ret
                except:
                    pass

                tbot.log.message(tbot.log.c(f"set bootmode {bm['name']} failed").red)
                raise RuntimeError(
                    f"Exit until callbacks work"
                )

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

            if "noethinit" in tbot.flags:
                return

            ethdevices = self.ethdevices[ini.generic_get_boardname()]
            for dev in ethdevices:
                ethdev = self.ethdevices[ini.generic_get_boardname()][dev]
                labdev = ethdev["labdevice"]
                out = self.exec0("ifconfig", "-a")
                if labdev not in out:
                    tbot.log.message(
                        tbot.log.c(
                            f"ethernet device {labdev} not found on lab host"
                        ).yellow
                    )
                    continue

                self.exec0("sudo", "ifconfig", labdev, "down", ethdev["serverip"], "up")
                out = self.exec0("ip", "link", "show", "dev", labdev)
                while "NO-CARRIER" in out:
                    self.exec0("sudo", "ethtool", "-s", labdev, "autoneg", "on")
                    time.sleep(1)
                    out = self.exec0("ip", "link", "show", "dev", labdev)

            labinit = []
            try:
                labinit = eval(cfgt.config_parser.get(LABSECTIONNAME, "labinit"))
            except:  # noqa: E722
                pass
            for i in labinit:
                self.exec0(linux.Raw(i))

    def has_sshmachine(self) -> bool:
        for s in cfgt.config_parser.sections():
            if "SSHMACHINE" in s:
                return True

        return False

    def sshmachine(self) -> linux.Bash:
        if self.has_sshmachine:
            return SSHMachine(self)

        return None


class SSHMachine(connector.SSHConnector, linux.Bash):
    try:
        name = cfgt.config_parser.get("SSHMACHINE", "name")
        username = cfgt.config_parser.get("SSHMACHINE", "username")
        port = cfgt.config_parser.get("SSHMACHINE", "port")
        hostname = cfgt.config_parser.get("SSHMACHINE", "hostname")
        wdir = cfgt.config_parser.get("SSHMACHINE", "workdir")
    except:
        pass

    def tftp_dir(self) -> "linux.path.Path[SSHMachine]":
        return self.workdir

    def toolsdir(self) -> "linux.path.Path[SSHMachine]":
        toolsdir = cfgt.config_parser.get("SSHMACHINE", "toolsdir")
        return linux.Path(self, toolsdir)

    @property
    def workdir(self) -> "linux.Path[SSHMachine]":
        return linux.Workdir.static(self, self.wdir)

    def init(self) -> None:
        # do stuff after login
        # self.exec0("uname", "-a")
        return None


def register_machines(ctx):
    ctx.register(GenericLab, tbot.role.LabHost)
    for s in cfgt.config_parser.sections():
        localfound = False
        if "BUILDHOST" in s:
            for f in tbot.flags:
                if "buildername:local" in f:
                    # build on machine, on which tbot is startet!
                    ctx.register(builders.genericbuilderlocal, tbot.role.BuildHost)
                    localfound = True

            if not localfound:
                ctx.register(builders.genericbuilder, tbot.role.BuildHost)

            return


FLAGS = {
    "local": "enable if labhost and tbot host are the same (use SubprocessConnector)",
    "yoctobuild": "use u-boot images from yocto build",
    "ssh": "use as boards console login with ssh",
    "withscript": "also load a script with uuu tool into ram",
    "uuuloader": "load SPL/U-Boot with uuu tool into RAM",
    "picocom": "use piccom for accessing serial console",
    "scriptcom": "use a script for accessing serial console",
    "tinkerforge": "use tinkerforge for switching power",
    "gpiopower": "use gpio pin for switching power",
    "powershellscript": "use a shell script for switching power",
    "poweroffonstart": "always power off board on tbot start",
    "labname": "select which labhost we use",
}
