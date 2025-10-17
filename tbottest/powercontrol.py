import abc
import hashlib
import tbot
import time
from tbot.machine import board
from tbot.machine import linux

from tbot_contrib.gpio import Gpio

__all__ = (
    "GpiopmControl",
    "PowerShellScriptControl",
    "SispmControl",
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

    def poweron(self) -> None:
        try:
            self._gpio
        except:  # noqa: E722
            self._gpio = Gpio(self.host, self.gpiopmctl_pin)
            self._gpio.set_direction("out")

        self._gpio.set_value(int(self.gpiopmctl_state))

    def poweroff(self) -> None:
        if "nopoweroff" in tbot.flags:
            tbot.log.message("Do not power off ...")
            return

        try:
            self._gpio
        except:  # noqa: E722
            self._gpio = Gpio(self.host, self.gpiopmctl_pin)
            self._gpio.set_direction("out")

        if int(self.gpiopmctl_state) == 1:
            self._gpio.set_value(False)
        else:
            self._gpio.set_value(True)

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


class TinkerforgeControl(board.PowerControl):
    """
    control Power On/off with Tinkerforge

    https://www.tinkerforge.com/

    **Example**: (board config)

    .. code-block:: python

        from tbot.machine import board
        from tbottest.powercontrol import Tinkerforge

        class MyControl(Tinkerforge, board.Board):
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
        from tbottest.powercontrol import TM021

        class MyControl(TM021, board.Board):
            device = "/dev/relais"
            baudrate = "500000"
            timeout = "5"
            address = "0"
            port = "1"
            debug = False
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
        if self.scriptexists == True:
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
                print("scriptname ", scriptname)
                print("script     ", script, type(script))
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

        self.host.exec0(self.hookdir / "tm021.py", self.tm021_device, self.tm021_baudrate,
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
            self.host.exec0(self.hookdir / "tm021.py", self.tm021_device, self.tm021_baudrate,
                self.tm021_timeout,
                self.tm021_address,
                self.tm021_port,
                "off",
                self.tm021_debug,
            )



FLAGS = {
    "nopoweroff": "Do not power off board at the end",
}
