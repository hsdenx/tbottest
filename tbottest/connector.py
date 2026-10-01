import abc
import contextlib
import time
import typing
from tbot.machine import channel, connector, linux

__all__ = (
    "KermitConnector",
    "PicocomConnector",
    "TelnetConnector",
)


class KermitConnector(connector.ConsoleConnector):
    """
    Connect to a serial console using kermit

    You can configure the device name using the ``kermit_cfg_file`` property.
    Additional command line options for kermit can be set using the
    ``kermit_options`` property.

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

    @property
    def kermit_options(self) -> typing.List[str]:
        """
        additional command line options passed to kermit before the
        config file, e.g. ``["-c", "-y"]``

        default: no additional options
        """
        return []

    @contextlib.contextmanager
    def kermitconnect(self, mach: linux.LinuxShell) -> channel.Channel:
        KERMIT_PROMPT = b"C-Kermit>"
        ch = mach.open_channel("kermit", *self.kermit_options, self.kermit_cfg_file)
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

    @property
    def slow_send_delay(self) -> typing.Optional[float]:
        """
        seconds to wait after each chunk sent to the console, see
        :py:attr:`tbot.machine.channel.Channel.slow_send_delay`

        Some consoles drop characters when a whole line arrives at once.

        default: None, keep the value of the channel
        """
        return None

    @property
    def slow_send_chunksize(self) -> typing.Optional[int]:
        """
        maximum number of bytes sent at once, see
        :py:attr:`tbot.machine.channel.Channel.slow_send_chunksize`

        default: None, keep the value of the channel
        """
        return None

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
        if self.slow_send_delay is not None:
            ch.slow_send_delay = self.slow_send_delay
        if self.slow_send_chunksize is not None:
            ch.slow_send_chunksize = self.slow_send_chunksize
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


class TelnetConnector(connector.ConsoleConnector):
    """
    Connect to a serial console via telnet (e.g. a terminal/console
    server exposing a serial line as a telnet port)

    You can configure host and port using the ``telnet_host`` and
    ``telnet_port`` properties.

    **Example**: (board config)

    .. code-block:: python

        from tbot.machine import board
        from tbottest.connector import TelnetConnector

        class MyBoard(TelnetConnector, board.Board):
            telnet_port = 2013

        BOARD = MyBoard
    """

    @property
    def telnet_host(self) -> str:
        """
        telnet host, default "localhost"
        """
        return "localhost"

    @property
    @abc.abstractmethod
    def telnet_port(self) -> int:
        """
        telnet port

        This property is **required**.
        """
        raise Exception("abstract method")

    @property
    def telnet_delay(self) -> float:
        """
        delay after exit, default 0.0
        """
        return 0.0

    @contextlib.contextmanager
    def telnetconnect(self, mach: linux.LinuxShell) -> channel.Channel:
        TELNET_PROMPT = b"telnet> "
        # telnet's own default escape character is also Ctrl-], the
        # same sequence tbot's interactive() uses to detach. Give it a
        # different one here so a user pressing Ctrl-] three times to
        # leave interactive() reaches tbot untouched instead of being
        # caught by telnet's own escape handling first.
        TELNET_ESCAPE = "T"
        ch = mach.open_channel(
            "telnet",
            "-e",
            "^" + TELNET_ESCAPE,
            self.telnet_host,
            str(self.telnet_port),
        )
        try:
            try:
                ret = ch.read(150, timeout=2)
                buf = ret.decode(errors="replace")
                # telnet tries every resolved address in turn (e.g. ::1
                # before 127.0.0.1) and reports "Connection refused" for
                # each one that does not answer, so that string alone
                # does not mean the connection failed overall; only
                # treat it as a failure if none of the attempts
                # succeeded.
                if "Connection refused" in buf and "Connected to" not in buf:
                    raise RuntimeError(f"telnet connection refused {buf}")
            except TimeoutError:
                pass

            yield ch
        finally:
            ch.sendcontrol(TELNET_ESCAPE)
            ch.read_until_prompt(TELNET_PROMPT)
            ch.sendline("quit")

            if self.telnet_delay != 0.0:
                time.sleep(self.telnet_delay)

    def connect(self, mach: linux.LinuxShell) -> channel.Channel:
        return self.telnetconnect(mach)


class ScriptConnector(connector.ConsoleConnector):
    """
    Connect to a serial console using a script

    **Example**: (board config)

    .. code-block:: python

        from tbot.machine import board
        from tbottest.connector import PicocomConnector

        class MyBoard(ScriptConnector, board.Board):
            scriptname = "connect"
            exitstring = ~~.
            boardname = wandboard

        BOARD = MyBoard
    """

    @property
    @abc.abstractmethod
    def boardname(self) -> str:
        """
        Name of the board

        This property is **required**.
        """
        raise Exception("abstract method")

    @property
    @abc.abstractmethod
    def exitstring(self) -> str:
        """
        string send to exit

        This property is **required**.
        """
        raise Exception("abstract method")

    @property
    @abc.abstractmethod
    def scriptname(self) -> str:
        """
        Name of the script

        This property is **required**.
        """
        raise Exception("abstract method")

    @contextlib.contextmanager
    def scriptconnect(self, mach: linux.LinuxShell, boardname) -> channel.Channel:
        ch = None
        try:
            ch = mach.open_channel(self.scriptname, boardname)
            yield ch
        finally:
            if ch is not None:
                ch.send(self.exitstring)

    def connect(self, mach: linux.LinuxShell) -> channel.Channel:
        return self.scriptconnect(mach, self.boardname)
