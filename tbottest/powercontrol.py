import abc
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


FLAGS = {
    "nopoweroff": "Do not power off board at the end",
}
