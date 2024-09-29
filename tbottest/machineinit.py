import abc
import contextlib
import typing
import tbot
from tbot.machine import machine
from tbot.machine import linux
from typing import List
import time

import platform

import ctypes

H = typing.TypeVar("H", bound=linux.LinuxShell)


class LauterbachLoad(machine.Initializer):
    """
    BIG FAT WARNING:

    I do not longer own a Lauterbach debugger, so may this class is broken


    TRACE32's configuration file "config.t32" has to contain these lines:
    RCL=NETASSIST
    PORT=20000
    The port value may be changed but has to match with the port number
    used with this python script.

    currently we use t32apicmd.py, but we used code from t32remotedo.py
    which does not work ... so need more rework!

    Also add in config.t32 the line

    CONNECTIONMODE=AUTOCONNECT

    so if you start trace32 and there is another running (or crashed)
    instance running, it get killed.
    """

    T32_OK = 0

    def trace32_execute_cmd(self) -> str:
        dllpath = f"{self.get_trace32_install_path()}/demo/api/python"
        print("DLL PATH ", dllpath)

        # auto-detect the correct library
        if (platform.system() == "Windows") or (platform.system()[0:6] == "CYGWIN"):
            if ctypes.sizeof(ctypes.c_voidp) == 4:
                # WINDOWS 32bit
                t32api = ctypes.CDLL(f"{dllpath}/t32api.dll")
                # alternative using windows DLL search order:
                #   t32api = ctypes.cdll.t32api
            else:
                # WINDOWS 64bit
                t32api = ctypes.CDLL(f"{dllpath}/t32api64.dll")
                # alternative using windows DLL search order:
                #   t32api = ctypes.cdll.t32api64
        elif platform.system() == "Darwin":
            # Mac OS X
            t32api = ctypes.CDLL(f"{dllpath}/t32api.dylib")
        else:
            if ctypes.sizeof(ctypes.c_voidp) == 4:
                # Linux 32bit
                t32api = ctypes.CDLL(f"{dllpath}/t32api.so")
            else:
                # Linux 64bit
                t32api = ctypes.CDLL(f"{dllpath}/t32api64.so")

        node = "localhost"
        port = "20000"
        packlen = "1024"
        if t32api.T32_Config(b"NODE=", node.encode("latin-1")) != self.T32_OK:
            print("invalid node: %s" % (node))
        if t32api.T32_Config(b"PACKLEN=", packlen.encode("latin-1")) != self.T32_OK:
            print("invalid packet length: %s" % (packlen))
        if t32api.T32_Config(b"PORT=", port.encode("latin-1")) != self.T32_OK:
            print("port number %s not accepted" % (port))
        print("Connecting...")
        if t32api.T32_Init() == self.T32_OK:
            print("Init okay")
            if t32api.T32_Attach(1) == self.T32_OK:
                print("Attach okay")
                if self._send_commands(t32api) != self.T32_OK:
                    t32api.T32_Exit()
            else:
                t32api.T32_Exit()
        else:
            t32api.T32_Exit()

    def _send_commands(self, t32api):
        for line in self.get_trace32_script():
            line = line.rstrip()
        if self.get_trace32_verbose() == "1":
            print(line)
        error = t32api.T32_Cmd(line.encode("latin-1"))
        if error != self.T32_OK:
            print('command failed: "%s"' % (line))

    def get_trace32_verbose(self) -> str:
        return "1"

    def get_trace32_install_path(self) -> str:
        """
            def get_trace32_path(self) -> str:
                return "/opt/t32"

        :rtype: str
        :returns: Path to the trace32 directory on your Host
        """
        return "/opt/t32"

    @abc.abstractmethod
    def get_trace32_cmd(self) -> str:
        """
            def get_trace32_path(self) -> str:
                return "/opt/t32/bin/pc_linux64/t32marm-qt"

        :rtype: str
        :returns: Path to the trace32 directory on your Host
        """
        pass

    @abc.abstractmethod
    def get_trace32_config(self) -> str:
        """
            def get_trace32_path(self) -> str:
                return "<pathto>/config.t32"

        :rtype: str
        :returns: Path to the config.t32 file on your Host
        """
        pass

    @abc.abstractmethod
    def get_trace32_script(self) -> str:
        """
            def get_trace32_path(self) -> str:
                return "<pathto>/autoboot.cmm"

        :rtype: str
        :returns: Path to the cript file on your Host
        """
        pass

    def get_host(self) -> linux.Bash:
        """
            def get_trace32_path(self) -> linux.Bash:
                return self.host

        :rtype: str
        :returns: Host on which the trace32 tool is installed
        """
        return self.host

    @contextlib.contextmanager
    def _init_machine(self) -> typing.Iterator:
        if "lauterbachloader" not in tbot.flags:
            yield None
            return

        tbot.log.message(
            tbot.log.c("Using Lauterbach debuggger for loading SPL/U-Boot").yellow
        )
        # cmd = self.get_trace32_cmd()
        # config = self.get_trace32_config()
        script = self.get_trace32_script()
        host = self.get_host()

        # we use API to communicate with trace32
        # so first start it
        # Now we can start trace32, but this starts a gui ...
        # and we get no info when script calls "go" ...
        # and we cannot execute this in background, as
        # if we execute it in  ssh machine, which may gets closed...
        # host.exec0(cmd, "-c", config, linux.Background)
        # host.exec0(cmd, "-c", config, "-s", script)

        # rework this, as not working
        # self.trace32_execute_cmd()
        # so use code from lauterbach installation...
        dllpath = f"{self.get_trace32_install_path()}/demo/api/python"
        host.exec0("cd", dllpath)
        host.exec0("python3", "t32apicmd.py", "do", script)

        # how to clear now receive buffer in channel from serial console ?

        # print("tbot.machine.channel.subprocess.SubprocessChannel ", tbot.machine.channel.subprocess.SubprocessChannel)
        # attrs = vars(tbot.machine.channel.subprocess.SubprocessChannel)
        # print(', '.join("%s: %s" % item for item in attrs.items()))
        # ub = tbot.selectable.Board
        # ub.ch.read_until_prompt()
        yield None


class SeggerLoad(machine.Initializer):
    """
    get the segger tools from
    https://www.segger.com/downloads/jlink/#J-LinkSoftwareAndDocumentationPack

    This class uses JLinkExe.
    """

    timeout = False
    name = "Segger"

    @abc.abstractmethod
    def get_segger_cmds(self) -> list:
        """
            def get_segger_cmds(self) -> str:
                return [{"cmd":"foo", "prompt":"pro1", {"cmd":"bar", "prompt":"por2"}]

        :rtype: list
        """
        pass

    def get_host(self) -> linux.Bash:
        """
            def get_host(self) -> linux.Bash:
                return self.host

        :rtype: str
        :returns: Host on which the segger tools are installed
        """
        return self.host

    def _send_one_cmd(self, host, cmd, prompt) -> bool:
        with host.ch.with_prompt(prompt):
            with tbot.log_event.command(self.name, cmd) as ev:
                host.ch.sendline(cmd, read_back=True)
                with host.ch.with_stream(ev, show_prompt=False):
                    out = host.ch.read_until_prompt()
                    if "go" in cmd:
                        if self.timeout is False:
                            # give SPL some time
                            time.sleep(2)
                            self.timeout = True
                ev.data["stdout"] = out

        # may we add here a check, if command was correct
        # unfortunately Segger JLinkExe has no return code,
        # so we need to check command output...
        #
        # we have command output now in ev.data["stdout"]
        #
        # add a list of strings/regular expressions and check them?
        # ToDo
        return True

    @contextlib.contextmanager
    def _init_machine(self) -> typing.Iterator:
        if "seggerloader" not in tbot.flags:
            yield None
            return

        tbot.log.message(
            tbot.log.c("Using Segger debuggger for loading SPL/U-Boot").yellow
        )
        cmds = self.get_segger_cmds()
        host = self.get_host()

        for cmd in cmds:
            ret = self._send_one_cmd(host, cmd["cmd"], cmd["prompt"])
            if ret is not True:
                raise RuntimeError(f"segger command {cmd['cmd']} failed")

        host.exec0("q")

        yield None


class UsbSdpLoad(machine.Initializer):
    """
    Machine-initializer for loading SPL/U-Boot image into
    RAM with imx_usb_loader tool from NXP and using
    Serial Download over USB

    source:
    https://github.com/boundarydevices/imx_usb_loader

    installation of tool:
    https://github.com/boundarydevices/imx_usb_loader/blob/master/README.md#installation

    **Example**: (board config)

    .. code-block:: python

        from tbot.machine import board
        from tbottest.powercontrol import SispmControl
        from tbottest.machineinit import UsbSdpLoad

        class MyControl(SispmControl, board.Board):
            sispmctl_device = "01:01:5c:29:39"
            sispmctl_port = "2"

        class MyControlLoadUB(MyControl, UsbSdpLoad):
            def get_imx_usb_loader(self):
                p = self.host.toolsdir()
                return p / "imx_usb_loader"

            def usb_loader_bins(self):
                p = self.host.yocto_result_dir()
                return [ p / "SPL.signed", p / "u-boot-ivt.img.signed"]

    This class sets also a tbot flag "usbloader"

    if passed to tbot, this class is active, if not passed
    this class does nothing.
    """

    @abc.abstractmethod
    def get_imx_usb_loader(self) -> linux.Path[H]:
        """
            def get_imx_usb_loader(self) -> linux.Path:
                return lh.workdir / "tools" / "imx_usb_loader"

        :rtype: linux.Path
        :returns: Path to the imx_usb_loader directory on your LabHost
        """
        pass

    @abc.abstractmethod
    def usb_loader_bins(self) -> List[str]:
        """
        return list of linux.Path to usb loader binaries

            def usb_loader_bins(self):
                p = self.host.yocto_result_dir()
                return [ p / "SPL.signed", p / "u-boot-ivt.img.signed"]

        This property is **required**.
        """
        raise Exception("abstract method")

    usb_loader_retry: int = 4
    """retry to load binary retry times"""

    @contextlib.contextmanager
    def _init_machine(self) -> typing.Iterator:
        if "usbloader" not in tbot.flags:
            yield None

        imx = self.get_imx_usb_loader()
        bins = self.usb_loader_bins()
        for bina in bins:
            loop = True
            i = 0
            time.sleep(3)
            while loop:
                if i:
                    time.sleep(2)
                ret, out = self.host.exec("sudo", imx / "imx_usb", bina)
                if "no matching USB device found" in out and ret == 1:
                    i += 1
                elif ret:
                    raise RuntimeError(f"imx_usb loader failed with {ret}")
                if "failed" in out:
                    raise RuntimeError(f"imx_usb loader failed with {out}")
                if "jumping to" in out:
                    loop = False
                elif i >= self.usb_loader_retry:
                    raise RuntimeError(
                        f"could not load {bina} with imx_usb_loader. retry {self.usb_loader_retry}"
                    )

        yield None


class UUULoad(machine.Initializer):
    """
    Machine-initializer for loading SPL/U-Boot image into
    RAM with uuu tool from NXP and using
    Serial Download over USB

    source:
    https://github.com/NXPmicro/mfgtools.git

    installation:
    https://github.com/NXPmicro/mfgtools#how-to-build

    We may can check if tool is installed and if not
    install it automagically...

    **Example**: (board config)

    .. code-block:: python

        from tbot.machine import board
        from tbottest.powercontrol import SispmControl
        from tbottest.machineinit import UUULoad

        class MyControl(SispmControl, board.Board):
            sispmctl_device = "01:01:5c:29:39"
            sispmctl_port = "2"

        class MyControlLoadUB(MyControl, UUULoad):
            def get_uuu_tool(self):
                return self.host.toolsdir()

            def uuu_loader_steps(self):
                p = self.host.yocto_result_dir()
                return [linux.Raw(f"SDP: boot -f /srv/tftpboot/SPL"),
                    linux.Raw(f"SDPV: delay 100"),
                    linux.Raw(f"SDPV: write -f /srv/tftpboot/u-boot-dtb.img -addr 0x877fffc0 -skipfhdr"),
                    linux.Raw(f"SDPV: jump -addr 0x877fffc0"),
                    ]

    This class sets also a tbot flag "uuuloader"

    if passed to tbot, this class is active, if not passed
    this class does nothing.
    """

    @abc.abstractmethod
    def get_uuu_tool(self) -> linux.Path[H]:
        """
            def get_uuu_tool(self) -> linux.Path:
                return lh.workdir / "tools"

        :rtype: linux.Path
        :returns: Path to the uuu directory on your LabHost
        """
        pass

    @abc.abstractmethod
    def uuu_loader_steps(self) -> List[str]:
        """
        return list of steps to do for uuu tool

            def uuu_loader_steps(self):
                p = self.host.yocto_result_dir()
                return [linux.Raw(f"SDP: boot -f /srv/tftpboot/SPL"),
                    linux.Raw(f"SDPV: delay 100"),
                    linux.Raw(f"SDPV: write -f /srv/tftpboot/u-boot-dtb.img -addr 0x877fffc0 -skipfhdr"),
                    linux.Raw(f"SDPV: jump -addr 0x877fffc0"),
                    ]

        This property is **required**.
        """
        raise Exception("abstract method")

    def _check_uuu_tool(self) -> bool:
        """
        check if uuu tool is installed and can be used.

        https://github.com/NXPmicro/mfgtools
        """
        uuu = self.get_uuu_tool()  # type: ignore
        ret, out = self.host.exec("sudo", "ls", uuu / "mfgtools/build/uuu/uuu")
        if ret != 0:
            # uuu tool not installed try to install
            tbot.log.message(
                tbot.log.c(f"mfgtools not installed in {uuu}. Try to install them").green
            )
            curdir = self.host.exec0("pwd").strip()
            self.host.exec0("cd", uuu)
            self.host.exec0("git", "clone", "https://github.com/NXPmicro/mfgtools")
            self.host.exec0("cd", "mfgtools")
            self.host.exec0("mkdir", "-p", "build")
            self.host.exec0("cd", "build")
            self.host.exec0("cmake", "..")
            self.host.exec0("make")
            self.host.exec0("cd", curdir)

        return True

    @contextlib.contextmanager
    def _init_machine(self) -> typing.Iterator:
        if "uuuloader" not in tbot.flags:
            yield None
            return

        if not self._check_uuu_tool():
            yield None
            return

        uuu = self.get_uuu_tool()  # type: ignore
        steps = self.uuu_loader_steps()  # type: List[str]
        for st in steps:
            self.host.exec0("sudo", uuu / "mfgtools/build/uuu/uuu", st)  # type: ignore

        yield None


FLAGS = {
    "lauterbachloader": "load SPL/UBoot with Lauterbach TRACE32",
    "seggerloader": "load SPL/UBoot with Segger JLinkExe",
    "usbloader": "load SPL / U-Boot images with imx_usb_loader",
    "uuuloader": "load images with uuu tool",
}
