import abc
import hashlib
import tbot
import time
import typing
from tbot.machine import board
from tbot.machine import linux

from tbot_contrib.gpio import Gpio

__all__ = (
    "GpiopmControl",
    "PowerShellScriptControl",
    "ShellyControl",
    "SispmControl",
    "TboxCtrlControl",
    "TinkerforgeControl",
    "TM021Control",
)


class GpiopmControl(board.PowerControl):
    """
    control Power On/off through a Gpio pin

    **Example**: (board config)

    .. code-block:: python

        from tbot.machine import board
        from tbottest.powercontrol import GpiopmControl

        class MyControl(GpiopmControl, board.Board):
            gpiopmctl_pin = "17"
            gpiopmctl_state = "1"
    """

    @property
    @abc.abstractmethod
    def gpiopmctl_pin(self) -> str:
        raise Exception("abstract method")

    @property
    @abc.abstractmethod
    def gpiopmctl_state(self) -> str:
        raise Exception("abstract method")

    def _ensure_gpio(self) -> Gpio:
        if not hasattr(self, "_gpio"):
            self._gpio = Gpio(self.host, self.gpiopmctl_pin)
            self._gpio.set_direction("out")
        return self._gpio

    def poweron(self) -> None:
        gpio = self._ensure_gpio()
        gpio.set_value(int(self.gpiopmctl_state))

    def poweroff(self) -> None:
        if "nopoweroff" in tbot.flags:
            tbot.log.message("Do not power off ...")
            return

        gpio = self._ensure_gpio()
        if int(self.gpiopmctl_state) == 1:
            gpio.set_value(False)
        else:
            gpio.set_value(True)

        tbot.log.message("Waiting a bit to let power settle down ...")
        time.sleep(2)


class PowerShellScriptControl(board.PowerControl):
    """
    control Power On/off with a shell script

    The shell script needs to evaluate the first parameter passed to
    the script. Values are:

    "on" for powering on the board

    "off" for powering off the board

    **Example**: (board config)

    .. code-block:: python

        from tbot.machine import board
        from tbottest.powercontrol import PowerShellScriptControl

        class MyControl(PowerShellScriptControl, board.Board):
            shell_script = "<path to shell script"
    """

    @property
    @abc.abstractmethod
    def shell_script(self) -> str:
        """
        shell command executed

        This property is **required**.
        """
        raise Exception("abstract method")

    def poweron(self) -> None:
        self.host.exec0(
            linux.Raw(self.shell_script),
            "on",
        )

    def poweroff(self) -> None:
        if "nopoweroff" in tbot.flags:
            tbot.log.message("Do not power off ...")
        else:
            self.host.exec0(
                linux.Raw(self.shell_script),
                "off",
            )


class ShellyControl(board.PowerControl):
    """
    control Power On/off with a Shelly device through shelly-ctrl

    https://github.com/EmbLux-Kft/shelly-ctrl

    shelly-ctrl runs on the lab host, which must reach the Shelly
    device in its network. By default tbot uses shelly-ctrl from the
    directory shelly-ctrl in the toolsdir of the lab host. If it is not
    there, tbot clones it into this directory and installs its python
    dependencies into a virtual environment .venv in it.

    **Example**: (board config)

    .. code-block:: python

        from tbot.machine import board
        from tbottest.powercontrol import ShellyControl

        class MyControl(ShellyControl, board.Board):
            shelly_device = "192.168.1.86"
            shelly_id = "0"
    """

    @property
    @abc.abstractmethod
    def shelly_device(self) -> str:
        """
        the Shelly device, given by IP, by MAC or by its mDNS name

        This property is **required**.
        """
        raise Exception("abstract method")

    @property
    def shelly_id(self) -> str:
        """
        channel of multi channel devices, default "0"
        """
        return "0"

    @property
    def shelly_command(self) -> typing.Optional[str]:
        """
        shelly-ctrl command on the lab host. Leave unset to use, and if
        needed install, shelly-ctrl in :py:meth:`shelly_tooldir`. A
        command given here is not installed, tbot stops if it is not
        found.
        """
        return None

    @property
    def shelly_tooldir(self) -> linux.Path:
        """
        directory of shelly-ctrl on the lab host, default shelly-ctrl
        in the toolsdir of the lab host
        """
        return self.host.toolsdir() / "shelly-ctrl"

    @property
    def shelly_repo(self) -> str:
        """
        git repository tbot clones shelly-ctrl from
        """
        return "https://github.com/EmbLux-Kft/shelly-ctrl.git"

    @property
    def shelly_timeout(self) -> typing.Optional[str]:
        """
        maximum time in seconds to look up MAC or mDNS name, leave unset
        to use the default of shelly-ctrl
        """
        return None

    def _shelly_install(self) -> list:
        d = self.shelly_tooldir
        python = d / ".venv/bin/python"
        script = d / "shelly-ctrl.py"

        ret, _ = self.host.exec("test", "-x", python)
        if ret == 0:
            ret, _ = self.host.exec("test", "-f", script)
        if ret != 0:
            tbot.log.message(
                tbot.log.c(f"shelly-ctrl not installed in {d}. Try to install it").green
            )
            ret, _ = self.host.exec("test", "-f", script)
            if ret != 0:
                self.host.exec0("mkdir", "-p", d.parent)
                self.host.exec0("git", "clone", self.shelly_repo, d)
            self.host.exec0("python3", "-m", "venv", d / ".venv")
            self.host.exec0(
                d / ".venv/bin/pip", "install", "-r", d / "requirements.txt"
            )

        return [python, script]

    def _shelly_cmd(self) -> list:
        if not hasattr(self, "_shelly_cmdline"):
            if self.shelly_command is None:
                self._shelly_cmdline = self._shelly_install()
            else:
                ret, _ = self.host.exec(
                    "command", "-v", linux.Raw(self.shelly_command)
                )
                if ret != 0:
                    raise RuntimeError(
                        f"shelly-ctrl command {self.shelly_command} not found on the lab host"
                    )
                self._shelly_cmdline = [linux.Raw(self.shelly_command)]
        return self._shelly_cmdline

    def _shelly_switch(self, state: str) -> str:
        cmd = self._shelly_cmd() + [
            "switch",
            self.shelly_device,
            state,
            "--id",
            str(self.shelly_id),
        ]
        if self.shelly_timeout is not None:
            cmd += ["-t", str(self.shelly_timeout)]
        return self.host.exec0(*cmd)

    def poweron(self) -> None:
        self._shelly_switch("on")

    def poweroff(self) -> None:
        if "nopoweroff" in tbot.flags:
            tbot.log.message("Do not power off ...")
            return

        self._shelly_switch("off")

        tbot.log.message("Waiting a bit to let power settle down ...")
        time.sleep(2)


class SispmControl(board.PowerControl):
    """
    control Power On/off with sispmctl

    http://sispmctl.sourceforge.net/

    **Example**: (board config)

    .. code-block:: python

        from tbot.machine import board
        from tbottest.powercontrol import SispmControl

        class MyControl(SispmControl, board.Board):
            sispmctl_device = "01:01:5c:29:39"
            sispmctl_port = "2"
    """

    @property
    @abc.abstractmethod
    def sispmctl_device(self) -> str:
        """
        Device used. Get device id with
        sispcmtl -s

        This property is **required**.
        """
        raise Exception("abstract method")

    @property
    @abc.abstractmethod
    def sispmctl_port(self) -> str:
        """
        port used.

        This property is **required**.
        """
        raise Exception("abstract method")

    def poweron(self) -> None:
        self.host.exec0("sispmctl", "-D", self.sispmctl_device, "-o", self.sispmctl_port)

    def poweroff(self) -> None:
        if "nopoweroff" in tbot.flags:
            tbot.log.message("Do not power off ...")
        else:
            self.host.exec0(
                "sispmctl", "-D", self.sispmctl_device, "-f", self.sispmctl_port
            )

            tbot.log.message("Waiting a bit to let power settle down ...")
            time.sleep(2)


class TboxCtrlControl(board.PowerControl):
    """
    control Power On/off through tbox-ctrl (a tbox SYSTEM Controller
    Modul, talking to the board over USB HID)

    https://gitlab.nabladev.com/nabla/tbox/tbox-ctrl

    **Example**: (board config)

    .. code-block:: python

        from tbot.machine import board
        from tbottest.powercontrol import TboxCtrlControl

        class MyControl(TboxCtrlControl, board.Board):
            tbox_powerpin = "P1_5V_EN"
    """

    @property
    @abc.abstractmethod
    def tbox_powerpin(self) -> str:
        """
        the tbox-firmware pin to switch, e.g. "P1_5V_EN", "P2_12V_EN",
        "P3_24V_EN", ... (see tbox-firmware/src/pins.h for the full list)

        This property is **required**.
        """
        raise Exception("abstract method")

    @property
    def tbox_vid(self) -> typing.Optional[int]:
        """
        optional USB VID override for tbox-ctrl's --vid - leave unset to
        use tbox-ctrl's own default (0x1209, pid.codes shared VID).
        """
        return None

    @property
    def tbox_pid(self) -> typing.Optional[int]:
        """
        optional USB PID override for tbox-ctrl's --pid - leave unset to
        use tbox-ctrl's own default (0x0001).
        """
        return None

    def _tbox_ctrl(self, *args: str) -> str:
        cmd = ["tbox-ctrl"]
        if self.tbox_vid is not None:
            cmd += ["--vid", hex(self.tbox_vid)]
        if self.tbox_pid is not None:
            cmd += ["--pid", hex(self.tbox_pid)]
        cmd += list(args)
        return self.host.exec0(*cmd)

    def poweron(self) -> None:
        self._tbox_ctrl("set", self.tbox_powerpin, "on")

    def poweroff(self) -> None:
        if "nopoweroff" in tbot.flags:
            tbot.log.message("Do not power off ...")
            return

        self._tbox_ctrl("set", self.tbox_powerpin, "off")


class TinkerforgeControl(board.PowerControl):
    """
    control Power On/off with Tinkerforge

    https://www.tinkerforge.com/

    **Example**: (board config)

    .. code-block:: python

        from tbot.machine import board
        from tbottest.powercontrol import TinkerforgeControl

        class MyControl(TinkerforgeControl, board.Board):
            channel = ""
            uid = ""
    """

    @property
    @abc.abstractmethod
    def channel(self) -> str:
        """
        channel used.

        This property is **required**.
        """
        raise Exception("abstract method")

    @property
    @abc.abstractmethod
    def uid(self) -> str:
        """
        uid

        This property is **required**.
        """
        raise Exception("abstract method")

    def poweron(self) -> None:
        self.host.exec0(
            "tinkerforge",
            "--host",
            self.host.hostname,
            "call",
            "industrial-dual-relay-bricklet",
            self.uid,
            "set-selected-value",
            self.channel,
            "false",
        )

    def poweroff(self) -> None:
        if "nopoweroff" in tbot.flags:
            tbot.log.message("Do not power off ...")
        else:
            self.host.exec0(
                "tinkerforge",
                "--host",
                self.host.hostname,
                "call",
                "industrial-dual-relay-bricklet",
                self.uid,
                "set-selected-value",
                self.channel,
                "true",
            )


TM021_SCRIPTS = {
    # scripts which tm021 uses:
    "TestModule.py": """\
class TestModule:
    def __init__(self, testBus, name, addr, debug=False):
        self.testBus = testBus
        self.name = name
        self.addr = addr
        self.debug = debug

    def send(self, scpiCmd):
        '''
        Send SCPI command to test module. No return value.
        '''
        snd = f'{self.name}#{self.addr}:{scpiCmd}\\r\\n'
        if self.debug:
            print(f'TX: {snd.strip()}')
        self.testBus.write(snd.encode())

    def sendCheck(self, scpiCmd):
        '''
        Send SCPI command to test module and check Error/Event Queue afterwards.
        '''
        self.send(scpiCmd)
        errNum, errStr = self.checkErrorQueue()
        if bool(int(errNum)):
            raise ConnectionError(f'{self.name}#{self.addr} reported an error: {errStr} ({errNum})')

    def receive(self):
        '''
        Receives a line from the test bus.
        '''
        line = self.testBus.readline().decode().strip()
        if self.debug:
            print(f'RX: {line}')

        if not line:
            raise ConnectionError(f'{self.name}#{self.addr} did not respond')

        _, name, addr, resp = line.split(',', 3)
        if name != self.name or addr != self.addr:
            raise ConnectionError(f'Wrong test module responded ({name}#{addr} instead of {self.name}#{self.addr})')

        return resp

    def sendReceive(self, scpiCmd):
        '''
        Sends and receives a line to/from the test bus.
        '''
        self.send(scpiCmd)
        return self.receive()

    def clearErrorQueue(self, queueSize=32):
        '''
        Clears the Error/Event Queue of the test module.
        '''
        self.send('*CLS')
        resp = self.sendReceive('SYST:ERR?')
        errNum, _ = resp.split(',', 1)
        if int(errNum) != 0:
            raise ConnectionError('Could not completely clear error queue')

    def checkErrorQueue(self):
        '''
        Returns SCPI error number and SCPI error string as tuple
        '''
        resp = self.sendReceive('SYST:ERR?')
        errNum, errStr = resp.split(',', 1)
        return (int(errNum), errStr)

    def wait(self, numTries=20):
        '''
        Tries to read *IDN? until the test module responds.
        The wait time depends on the timeout of the testBus and numTries.
        The default numTries value assumes 1 second timeout.
        This function is useful in case the test module has blocking operations,
        that take a long time. No return value.
        '''
        for i in range(numTries):
            try:
                _ = self.sendReceive('*IDN?')
            except ConnectionError:
                continue
            try:
                self.clearErrorQueue()
            except ConnectionError:
                pass
            return
        raise ConnectionError(f'Waiting for {self.name}#{self.addr} failed, it never responded')
""",
    # Script which tbot uses for tm021 access:
    "tm021.py": """\
#!/usr/bin/env python3

import serial # pySerial
import sys

from TestModule import TestModule

# 1 : device
# 2 : baudrate
# 3 : timeout
# 4 : address
# 5 : port
# 6 : on or off
# 7 : debug


testBus = serial.Serial(str(sys.argv[1]), int(sys.argv[2]), timeout=int(sys.argv[3]))
if sys.argv[7] == "True":
    print ("ARGS ", sys.argv)

tm021addr0 = TestModule(testBus, 'TM021', str(sys.argv[4]), debug=sys.argv[7])

tm021addr0.clearErrorQueue()
tm021addr0.sendCheck('SYST:REM')

state = "OPEN"
if sys.argv[6] == "on":
    state = "CLOS"

tmp = f"ROUT:{state} (@{sys.argv[5]})"
tm021addr0.sendCheck(tmp)
response=tm021addr0.sendReceive('ROUT:CLOS? (@1)')
print ("RESP ", response)
""",
}


class TM021Control(board.PowerControl):
    """
    control Power On/off with DH Electronics
    TM-021 4-fach Relaismodul

    https://www.dh-electronics.com

    **Example**: (board config)

    .. code-block:: python

        from tbot.machine import board
        from tbottest.powercontrol import TM021Control

        class MyControl(TM021Control, board.Board):
            tm021_device = "/dev/relais"
            tm021_baudrate = "500000"
            tm021_timeout = "5"
            tm021_address = "0"
            tm021_port = "1"
            tm021_debug = False
    """
    scriptexists = False

    @property
    @abc.abstractmethod
    def tm021_baudrate(self) -> str:
        """
        Baudrate for serial device
        """
        return 500000

    @property
    @abc.abstractmethod
    def tm021_timeout(self) -> str:
        """
        timeout for one command in seconds
        """
        return 5

    @property
    @abc.abstractmethod
    def tm021_device(self) -> str:
        """
        linux device used.

        This property is **required**.
        """
        raise Exception("abstract method")

    @property
    @abc.abstractmethod
    def tm021_address(self) -> str:
        """
        The address of the relais

        This property is **required**.
        """
        raise Exception("abstract method")

    @property
    @abc.abstractmethod
    def tm021_port(self) -> str:
        """
        The port of the relais

        This property is **required**.
        """
        raise Exception("abstract method")

    @property
    @abc.abstractmethod
    def tm021_debug(self) -> str:
        """
        Enable debug traces
        """
        return "False"

    def copy_script(self) -> bool:
        if self.scriptexists:
            return True

        self.hookdir = linux.Path(self.host, "/tmp/tbot/tm021")
        self.host.exec0("mkdir", "-p", self.hookdir)
        # Generate a hash for the version of the control files
        script_hasher = hashlib.sha256()
        for script in sorted(TM021_SCRIPTS.values()):
            script_hasher.update(script.encode("utf-8"))
        script_hash = script_hasher.hexdigest()

        hashfile = self.hookdir / "tbot-scripts.sha256"
        try:
            up_to_date = script_hash == hashfile.read_text().strip()
        except Exception:
            up_to_date = False

        if up_to_date:
            tbot.log.message("Hooks are up to date, skipping deployment ...")
        else:
            tbot.log.message("Updating hook scripts ...")

            for scriptname, script in TM021_SCRIPTS.items():
                tbot.log.message(f"scriptname {scriptname}")
                tbot.log.message(f"script     {script} {type(script)}")
                (self.hookdir / scriptname).write_text(script)
                self.host.exec0("chmod", "+x", self.hookdir / scriptname)

            # Write checksum so we don't re-deploy next time
            hashfile.write_text(script_hash)

        self.scriptexists = True
        return True

    def poweron(self) -> None:
        # we cannot use pyserial as device is on lab host, and tbot
        # may is not started on lab host!
        self.copy_script()

        self.host.exec0(
            self.hookdir / "tm021.py",
            self.tm021_device,
            self.tm021_baudrate,
            self.tm021_timeout,
            self.tm021_address,
            self.tm021_port,
            "on",
            self.tm021_debug,
        )

    def poweroff(self) -> None:
        if "nopoweroff" in tbot.flags:
            tbot.log.message("Do not power off ...")
        else:
            # power_check() may call poweroff() directly (-f
            # poweroffonstart) without a prior poweron() on this
            # instance, so self.hookdir isn't guaranteed to be set yet
            self.copy_script()

            self.host.exec0(
                self.hookdir / "tm021.py",
                self.tm021_device,
                self.tm021_baudrate,
                self.tm021_timeout,
                self.tm021_address,
                self.tm021_port,
                "off",
                self.tm021_debug,
            )


FLAGS = {
    "nopoweroff": "Do not power off board at the end",
}
