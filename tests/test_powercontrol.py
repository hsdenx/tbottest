"""
Unit tests for tbottest/powercontrol.py's GpiopmControl and
TM021Control.

GpiopmControl is tested against a stub tbot_contrib.gpio.Gpio (the
real one talks to a live /sys/class/gpio, see conftest's
install_gpio_stub). TM021Control's copy_script()/poweron()/poweroff()
are tested against a real temp directory (via a small linux.Path
stand-in scoped to tmp_path) and a FakeHost that only understands
enough of exec0() to make "mkdir -p" actually create the directory,
since copy_script()'s hashfile.read_text()/write_text() do real I/O.

PowerShellScriptControl/SispmControl/TinkerforgeControl are pure
exec0() one-liners with no cached/lazily-initialized state, so they
are not covered here.
"""

import os
import pathlib
import sys

from conftest import install_gpio_stub, load_module

install_gpio_stub()

powercontrol = load_module(
    "tbottest_powercontrol",
    os.path.join(os.path.dirname(__file__), "..", "tbottest", "powercontrol.py"),
)

Gpio = powercontrol.Gpio  # the FakeGpio installed by install_gpio_stub()


class FakeGpioHost:
    hostname = "fakehost"


def make_gpio_control(pin="17", state="1"):
    class Ctl(powercontrol.GpiopmControl):
        gpiopmctl_pin = pin
        gpiopmctl_state = state
        host = FakeGpioHost()

    return Ctl()


class TestGpiopmControl:
    def test_poweron_sets_configured_state(self):
        ctl = make_gpio_control(state="1")
        ctl.poweron()
        assert ctl._gpio.value == 1
        assert ctl._gpio.direction == "out"

    def test_gpio_instance_is_created_once_and_reused(self):
        ctl = make_gpio_control()
        ctl.poweron()
        gpio_after_poweron = ctl._gpio
        ctl.poweroff()
        assert ctl._gpio is gpio_after_poweron

    def test_poweroff_inverts_active_high_state(self):
        ctl = make_gpio_control(state="1")
        ctl.poweroff()
        assert ctl._gpio.value is False

    def test_poweroff_inverts_active_low_state(self):
        ctl = make_gpio_control(state="0")
        ctl.poweroff()
        assert ctl._gpio.value is True

    def test_poweroff_respects_nopoweroff_flag(self):
        ctl = make_gpio_control()
        ctl.poweron()
        sys.modules["tbot"].flags = {"nopoweroff"}
        ctl._gpio.value = "untouched"
        ctl.poweroff()
        assert ctl._gpio.value == "untouched"


class _FakeTm021Path:
    """A linux.Path stand-in confined to a tmp_path, so
    TM021Control.copy_script()'s real hashfile.read_text()/write_text()
    calls land in the test's temp directory instead of the real
    /tmp/tbot/tm021 on the machine running the tests."""

    def __init__(self, base: pathlib.Path, rel: str = ""):
        self._base = base
        self._p = base / rel.lstrip("/") if rel else base

    def _with(self, p: pathlib.Path) -> "_FakeTm021Path":
        new = _FakeTm021Path.__new__(_FakeTm021Path)
        new._base = self._base
        new._p = p
        return new

    def __truediv__(self, other):
        return self._with(self._p / str(other))

    def read_text(self):
        return self._p.read_text()

    def write_text(self, data):
        self._p.write_text(data)

    def __fspath__(self):
        return str(self._p)

    def __str__(self):
        return str(self._p)


class FakeTm021Host:
    def __init__(self):
        self.commands = []

    def exec0(self, *args):
        self.commands.append(tuple(str(a) for a in args))
        if args and args[0] == "mkdir" and "-p" in args:
            pathlib.Path(str(args[-1])).mkdir(parents=True, exist_ok=True)
        return ""


def make_tm021_control(tmp_path, monkeypatch):
    # copy_script() always constructs its one linux.Path root as
    # linux.Path(self.host, "/tmp/tbot/tm021"); map that root directly
    # onto tmp_path so file-existence assertions can use tmp_path
    # itself, and let __truediv__ handle everything relative to it.
    monkeypatch.setattr(
        powercontrol.linux, "Path", lambda host, p="": _FakeTm021Path(tmp_path)
    )

    class Ctl(powercontrol.TM021Control):
        tm021_device = "/dev/relais"
        tm021_baudrate = "500000"
        tm021_timeout = "5"
        tm021_address = "0"
        tm021_port = "1"
        tm021_debug = False
        host = FakeTm021Host()

    return Ctl()


class TestTm021ControlCopyScript:
    def test_first_deployment_writes_scripts_and_hashfile(self, tmp_path, monkeypatch):
        ctl = make_tm021_control(tmp_path, monkeypatch)
        ctl.copy_script()

        assert (tmp_path / "tbot-scripts.sha256").exists()
        for scriptname in powercontrol.TM021_SCRIPTS:
            assert (tmp_path / scriptname).exists()
        assert ctl.scriptexists is True

    def test_second_call_is_a_noop_via_scriptexists_cache(self, tmp_path, monkeypatch):
        ctl = make_tm021_control(tmp_path, monkeypatch)
        ctl.copy_script()
        (tmp_path / "TestModule.py").write_text("stale content")
        ctl.copy_script()
        # scriptexists short-circuits copy_script() entirely, so the
        # tampered file is left untouched
        assert (tmp_path / "TestModule.py").read_text() == "stale content"

    def test_fresh_instance_skips_redeploy_when_hash_matches(self, tmp_path, monkeypatch):
        make_tm021_control(tmp_path, monkeypatch).copy_script()
        before = (tmp_path / "TestModule.py").read_text()

        ctl2 = make_tm021_control(tmp_path, monkeypatch)
        ctl2.copy_script()
        after = (tmp_path / "TestModule.py").read_text()
        assert before == after

    def test_fresh_instance_redeploys_when_hashfile_missing(self, tmp_path, monkeypatch):
        ctl = make_tm021_control(tmp_path, monkeypatch)
        ctl.copy_script()
        (tmp_path / "tbot-scripts.sha256").unlink()

        ctl2 = make_tm021_control(tmp_path, monkeypatch)
        ctl2.copy_script()
        assert (tmp_path / "tbot-scripts.sha256").exists()


class TestTm021ControlPowerOnOff:
    def test_poweron_sends_on_command(self, tmp_path, monkeypatch):
        ctl = make_tm021_control(tmp_path, monkeypatch)
        ctl.poweron()
        last = ctl.host.commands[-1]
        assert last[-2] == "on"

    def test_poweroff_without_prior_poweron_does_not_raise(self, tmp_path, monkeypatch):
        """
        Regression test: poweroff() used to reference self.hookdir
        without ever calling copy_script() itself, relying entirely on
        a prior poweron() call on the *same* instance to have set it.
        labgeneric.py's boardTMControl.power_check() calls
        self.poweroff() directly (-f poweroffonstart) on a fresh
        instance, which used to raise AttributeError.
        """
        ctl = make_tm021_control(tmp_path, monkeypatch)
        ctl.poweroff()  # must not raise
        last = ctl.host.commands[-1]
        assert last[-2] == "off"

    def test_poweroff_respects_nopoweroff_flag(self, tmp_path, monkeypatch):
        ctl = make_tm021_control(tmp_path, monkeypatch)
        sys.modules["tbot"].flags = {"nopoweroff"}
        ctl.poweroff()
        assert ctl.host.commands == []
