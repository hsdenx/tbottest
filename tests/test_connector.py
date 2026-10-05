"""
Unit tests for tbottest/connector.py's TelnetConnector.

connector.py is loaded directly via load_module() (bypassing
tbottest/__init__.py, which patches tbot.log_event.command() and
needs a populated tbot.flags), against a FakeMach/FakeChannel pair
that record the open_channel() arguments and the exit-sequence calls
(sendcontrol()/read_until_prompt()/sendline()).

Relies on conftest.py's own module-level install_tbot_stubs() call for
tbot.machine.{channel,connector,linux} rather than calling it again
here: a second call replaces sys.modules["tbot"] with a fresh module,
and conftest's _reset_tbot_flags autouse fixture then resets flags on
that new module while any test file collected before this one is
still holding a reference to the original, so its flags stop getting
reset between tests.
"""

import os

import pytest

from conftest import load_module

connector = load_module(
    "tbottest_connector",
    os.path.join(os.path.dirname(__file__), "..", "tbottest", "connector.py"),
)


class FakeChannel:
    def __init__(self, initial_read: bytes = b""):
        self.sent = []
        self._initial_read = initial_read
        self._read_done = False

    def read(self, n, timeout=None):
        if not self._read_done:
            self._read_done = True
            if self._initial_read:
                return self._initial_read
        raise TimeoutError()

    def sendcontrol(self, c):
        self.sent.append(("ctrl", c))

    def read_until_prompt(self, prompt):
        self.sent.append(("prompt", prompt))
        return ""

    def sendline(self, s):
        self.sent.append(("line", s))


class FakeMach:
    def __init__(self, initial_read: bytes = b""):
        self.args = None
        self._initial_read = initial_read

    def open_channel(self, *args):
        self.args = args
        return FakeChannel(self._initial_read)


class Board(connector.TelnetConnector):
    telnet_port = 2013


class BoardCustomHost(connector.TelnetConnector):
    telnet_host = "console-server"
    telnet_port = 7000


class TestTelnetConnectDefaults:
    def test_default_host_is_localhost(self):
        assert Board().telnet_host == "localhost"

    def test_default_delay_is_zero(self):
        assert Board().telnet_delay == 0.0


class TestTelnetConnect:
    def test_opens_with_noncolliding_escape_char_and_host_port(self):
        mach = FakeMach()
        with Board().telnetconnect(mach) as ch:
            assert mach.args == ("telnet", "-e", "^T", "localhost", "2013")
        assert ch is not None

    def test_uses_custom_host_and_port(self):
        mach = FakeMach()
        with BoardCustomHost().telnetconnect(mach):
            pass
        assert mach.args == ("telnet", "-e", "^T", "console-server", "7000")

    def test_exit_sequence_sends_escape_then_prompt_then_quit(self):
        mach = FakeMach()
        with Board().telnetconnect(mach) as ch:
            pass
        assert ch.sent == [
            ("ctrl", "T"),
            ("prompt", b"telnet> "),
            ("line", "quit"),
        ]

    def test_connect_delegates_to_telnetconnect(self):
        mach = FakeMach()
        with Board().connect(mach) as ch:
            assert mach.args == ("telnet", "-e", "^T", "localhost", "2013")

    def test_no_initial_output_is_not_an_error(self):
        mach = FakeMach()
        with Board().telnetconnect(mach):
            pass  # must not raise despite the read() timing out

    def test_ipv6_then_ipv4_connection_refused_is_not_an_error(self):
        # telnet tries every resolved address in turn; a "Connection
        # refused" for an earlier one (here ::1) is not fatal as long
        # as a later one (127.0.0.1) succeeds.
        buf = (
            b"Trying ::1...\r\n"
            b"telnet: connect to address ::1: Connection refused\r\n"
            b"Trying 127.0.0.1...\r\n"
            b"Connected to localhost.\r\n"
            b"Escape character is '^T'.\r\n"
        )
        mach = FakeMach(initial_read=buf)
        with Board().telnetconnect(mach):
            pass  # must not raise

    def test_all_addresses_refused_raises(self):
        buf = (
            b"Trying ::1...\r\n"
            b"telnet: connect to address ::1: Connection refused\r\n"
            b"Trying 127.0.0.1...\r\n"
            b"telnet: connect to address 127.0.0.1: Connection refused\r\n"
        )
        mach = FakeMach(initial_read=buf)
        with pytest.raises(RuntimeError, match="telnet connection refused"):
            with Board().telnetconnect(mach):
                pass


class PicocomChannel(FakeChannel):
    def __init__(self):
        super().__init__()
        self.slow_send_delay = 0.01
        self.slow_send_chunksize = 8


class PicocomMach(FakeMach):
    def open_channel(self, *args):
        self.args = args
        self.ch = PicocomChannel()
        return self.ch


class PicocomBoard(connector.PicocomConnector):
    baudrate = "115200"
    device = "/dev/ttyUSB0"


class PicocomBoardSlow(PicocomBoard):
    slow_send_delay = 0.02
    slow_send_chunksize = 1


class TestPicocomSlowSend:
    def test_defaults_keep_channel_values(self):
        mach = PicocomMach()
        with PicocomBoard().picocomconnect(mach) as ch:
            assert ch.slow_send_delay == 0.01
            assert ch.slow_send_chunksize == 8

    def test_configured_values_reach_channel(self):
        mach = PicocomMach()
        with PicocomBoardSlow().picocomconnect(mach) as ch:
            assert ch.slow_send_delay == 0.02
            assert ch.slow_send_chunksize == 1

    def test_args_unchanged(self):
        mach = PicocomMach()
        with PicocomBoardSlow().picocomconnect(mach):
            pass
        assert mach.args == ("picocom", "-b", "115200", "-l", "/dev/ttyUSB0")


def test_all_lists_every_connector():
    defined = sorted(
        name
        for name, obj in vars(connector).items()
        if isinstance(obj, type)
        and obj.__module__ == connector.__name__
        and name.endswith("Connector")
    )
    assert defined
    assert sorted(connector.__all__) == defined
