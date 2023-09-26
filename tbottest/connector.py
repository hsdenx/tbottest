import abc
import contextlib
import time
from tbot.machine import channel, connector, linux

__all__ = (
    "KermitConnector",
    "PicocomConnector",
)


class KermitConnector(connector.ConsoleConnector):
    """
    Connect to a serial console using kermit

    You can configure the device name using the ``kermit_cfg_file`` property.

    **Example**: (board config)

    .. code-block:: python

        from tbot.machine import board
        from tbottest.connector import KermitConnector

        class MyBoard(KermitConnector, board.Board):
            kermit_cfg_file = "path to config file"

        BOARD = MyBoard
    """

    @property
    def kermit_delay(self) -> float:
        """
        delay after exit, default None
        """
        return 0.0

    @property
    @abc.abstractmethod
    def kermit_cfg_file(self) -> str:
        """
        kermit config file

        This property is **required**.
        """
        raise Exception("abstract method")

    @contextlib.contextmanager
    def kermitconnect(self, mach: linux.LinuxShell) -> channel.Channel:
        KERMIT_PROMPT = b"C-Kermit>"
        ch = mach.open_channel("kermit", self.kermit_cfg_file)
        try:
            try:
                ret = ch.read(150, timeout=2)
                buf = ret.decode(errors="replace")
                if "Locked" in buf:
                    raise RuntimeError(f"serial line is locked {buf}")
            except TimeoutError:
                pass

            yield ch
        finally:
            ch.sendcontrol("\\")
            ch.send("C")
            ch.read_until_prompt(KERMIT_PROMPT)
            ch.sendline("exit")

            # get original prompt...
            if self.kermit_delay != 0.0:
                time.sleep(self.kermit_delay)

    def connect(self, mach: linux.LinuxShell) -> channel.Channel:
        return self.kermitconnect(mach)


class PicocomConnector(connector.ConsoleConnector):
    """
    Connect to a serial console using picocom



    **Example**: (board config)

    .. code-block:: python

        from tbot.machine import board
        from tbottest.connector import PicocomConnector

        class MyBoard(PicocomConnector, board.Board):
            baudrate = 115200
            device = /dev/serial/by-id/usb-Prolific_Technology_Inc._USB-Serial_Controller-if00-port0
            noreset

        BOARD = MyBoard
    """

    @property
    def delay(self) -> float:
        """
        delay after exit, default None
        """
        return 0.0

    @property
    @abc.abstractmethod
    def baudrate(self) -> str:
        """
        baudrate (picocom argument -b)

        This property is **required**.
        """
        raise Exception("abstract method")

    @property
    @abc.abstractmethod
    def device(self) -> str:
        """
        tty device (argument -l)

        This property is **required**.
        """
        raise Exception("picocom abstract method")

    @property
    def noreset(self) -> bool:
        """
        Pass -r picocom argument

        picocom manual says:
        If given, picocom will not reset the serial port when exiting.
        It will just close the respective filedescriptor and do nothing more.
        The serial port settings will not be restored to their original values and,
        unless the --hangup option is also given, the modem-control lines will not
        beaffected.  This is useful, for example, for leaving modems connected when
        exiting picocom. Regardless whether the --noreset option is given, the user
        can exit picocom using the "Quit"command (instead of "Exit"), which makes
        picocom behave exactly as if --noreset was given. See also the --hangup option.

        (Default: Disabled)

        NOTICE: Picocom clears the modem control lines on exit by setting the HUPCL
        control bit of therespective port. Picocom always sets HUPCL according to the
        --noreset and --hangup options. If --noreset is given and --hangup is not, then
        HUPCL for the port is cleared and will remain soafter exiting picocom.
        If --noreset is not given, or if both --noreset and --hangup are given, then
        HUPCL is set for the port and will remain so after exiting picocom. This is
        true, regardless ofthe way picocom terminates (command, read zero-bytes from
        standard input, killed by signal,fatal error, etc), and regardless of the
        --noinit option.
        """
        return False

    @contextlib.contextmanager
    def picocomconnect(self, mach: linux.LinuxShell) -> channel.Channel:
        args = []
        if self.noreset:
            args.append("-r")

        args.append("-b")
        args.append(self.baudrate)
        args.append("-l")
        args.append(self.device)

        ch = mach.open_channel("picocom", *args)
        try:
            yield ch
        finally:
            ch.sendcontrol("A")
            ch.sendcontrol("Q")

            # some usb adapters need here an delay...
            if self.delay != 0.0:
                time.sleep(self.delay)

    def connect(self, mach: linux.LinuxShell) -> channel.Channel:
        return self.picocomconnect(mach)
