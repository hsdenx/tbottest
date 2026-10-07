"""
Unit tests for tbottest/powercontrol.py's GpiopmControl,
PowerShellScriptControl, ShellyControl, SispmControl and TM021Control.

GpiopmControl is tested against a stub tbot_contrib.gpio.Gpio (the
real one talks to a live /sys/class/gpio, see conftest's
install_gpio_stub). PowerShellScriptControl/ShellyControl/SispmControl are
tested via a FakeExecHost that just records exec0() calls, since they are
pure one-liners with no cached/lazily-initialized state.
TM021Control's copy_script()/poweron()/poweroff() are tested against
a real temp directory (via a small linux.Path stand-in scoped to
tmp_path) and a FakeHost that only understands enough of exec0() to
make "mkdir -p" actually create the directory, since
copy_script()'s hashfile.read_text()/write_text() do real I/O.

TinkerforgeControl is not covered here: it is also a pure exec0()
one-liner (same shape as SispmControl), left out only because no
Tinkerforge-specific behavior needed a regression test.
"""

import os
import pathlib
import sys

import pytest

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


class FakeExecHost:
    hostname = "fakehost"

    def __init__(self):
        self.commands = []

    def exec0(self, *args):
        self.commands.append(tuple(str(a) for a in args))
        return ""


def make_shell_control(script="/opt/power.sh"):
    class Ctl(powercontrol.PowerShellScriptControl):
        shell_script = script
        host = FakeExecHost()

    return Ctl()


class TestPowerShellScriptControl:
    def test_poweron_runs_script_with_on(self):
        ctl = make_shell_control()
        ctl.poweron()
        assert ctl.host.commands == [("/opt/power.sh", "on")]

    def test_poweroff_runs_script_with_off(self):
        ctl = make_shell_control()
        ctl.poweroff()
        assert ctl.host.commands == [("/opt/power.sh", "off")]

    def test_poweroff_respects_nopoweroff_flag(self):
        ctl = make_shell_control()
        sys.modules["tbot"].flags = {"nopoweroff"}
        ctl.poweroff()
        assert ctl.host.commands == []


class ShellyPath(pathlib.PurePosixPath):
    """linux.Path stand-in, with the _local_str() tbot's Path has"""

    def _local_str(self):
        return str(self)


class FakeShellyHost:
    """Records exec0() calls; exec() answers "test -x/-f" from the set
    of existing files and "command -v" from the set of known commands,
    and git clone creates the files of the shelly-ctrl checkout, so the
    install steps can be followed."""

    def __init__(self, files=(), commands=(), name="lab"):
        self.files = set(files)
        self.known_commands = set(commands)
        self.commands = []
        self.name = name

    def toolsdir(self):
        return ShellyPath("/opt/tools")

    def exec(self, *args):
        args = tuple(str(a) for a in args)
        self.commands.append(args)
        if args[0] == "test":
            return (0 if args[2] in self.files else 1), ""
        if args[:2] == ("command", "-v"):
            if args[2] in self.known_commands:
                return 0, f"/usr/local/bin/{args[2]}\n"
            return 1, ""
        raise AssertionError(f"unexpected exec {args}")

    def exec0(self, *args):
        args = tuple(str(a) for a in args)
        self.commands.append(args)
        if args[:2] == ("git", "clone"):
            self.files.add(args[3] + "/shelly-ctrl.py")
        if args[:3] == ("python3", "-m", "venv"):
            self.files.add(args[3] + "/bin/python")
        return ""


SHELLYDIR = "/opt/tools/shelly-ctrl"
SHELLYPY = SHELLYDIR + "/.venv/bin/python"
SHELLYSCRIPT = SHELLYDIR + "/shelly-ctrl.py"
INSTALLED = (SHELLYPY, SHELLYSCRIPT)


def make_shelly_control(host=None, **props):
    attrs = {
        "shelly_device": "192.168.1.86",
        "host": host or FakeShellyHost(INSTALLED),
    }
    attrs.update(props)
    Ctl = type("Ctl", (powercontrol.ShellyControl,), attrs)
    return Ctl()


@pytest.fixture(autouse=True)
def forget_shelly_ctrl():
    # the place of shelly-ctrl is kept for the whole run, start every
    # test without it
    powercontrol._SHELLY_CMDLINE.clear()


def lookups(host):
    return [c for c in host.commands if c[0] in ("test", "command")]


def switches(ctl):
    return [c for c in ctl.host.commands if "switch" in c]


def installs(ctl):
    return [
        c
        for c in ctl.host.commands
        if c[0] in ("mkdir", "git", "python3") or c[0].endswith("/pip")
    ]


class TestShellyControl:
    def test_poweron_switches_channel_0_on_by_default(self):
        ctl = make_shelly_control()
        ctl.poweron()
        assert switches(ctl) == [
            (SHELLYPY, SHELLYSCRIPT, "switch", "192.168.1.86", "on", "--id", "0")
        ]
        assert installs(ctl) == []

    def test_poweroff_switches_off(self, monkeypatch):
        monkeypatch.setattr(powercontrol.time, "sleep", lambda s: None)
        ctl = make_shelly_control()
        ctl.poweroff()
        assert switches(ctl) == [
            (SHELLYPY, SHELLYSCRIPT, "switch", "192.168.1.86", "off", "--id", "0")
        ]

    def test_looked_up_once_per_run(self, monkeypatch):
        monkeypatch.setattr(powercontrol.time, "sleep", lambda s: None)
        host = FakeShellyHost(INSTALLED)
        ctl = make_shelly_control(host)
        ctl.poweron()
        ctl.poweroff()
        first = len(lookups(host))
        assert first > 0
        # a new instance, as every board machine and power testcase has
        make_shelly_control(host).poweron()
        assert len(lookups(host)) == first
        assert len(switches(ctl)) == 3

    def test_looked_up_per_lab_host(self):
        make_shelly_control(FakeShellyHost(INSTALLED, name="lab1")).poweron()
        host2 = FakeShellyHost(name="lab2")
        ctl2 = make_shelly_control(host2)
        ctl2.poweron()
        assert installs(ctl2) != []

    def test_command_in_path_is_used(self):
        host = FakeShellyHost(commands=["shelly-ctrl.py"])
        ctl = make_shelly_control(host)
        ctl.poweron()
        assert switches(ctl) == [
            ("shelly-ctrl.py", "switch", "192.168.1.86", "on", "--id", "0")
        ]
        assert installs(ctl) == []
        assert [c for c in host.commands if c[0] == "test"] == []

    def test_command_in_path_wins_over_tooldir(self):
        ctl = make_shelly_control(FakeShellyHost(INSTALLED, commands=["shelly-ctrl.py"]))
        ctl.poweron()
        assert switches(ctl)[0][0] == "shelly-ctrl.py"

    def test_missing_shelly_ctrl_is_cloned_and_installed(self):
        ctl = make_shelly_control(FakeShellyHost())
        ctl.poweron()
        assert installs(ctl) == [
            ("mkdir", "-p", "/opt/tools"),
            ("git", "clone", "https://github.com/EmbLux-Kft/shelly-ctrl.git", SHELLYDIR),
            ("python3", "-m", "venv", SHELLYDIR + "/.venv"),
            (SHELLYDIR + "/.venv/bin/pip", "install", "-r", SHELLYDIR + "/requirements.txt"),
        ]
        # installed before it is used
        assert ctl.host.commands[-1][:3] == (SHELLYPY, SHELLYSCRIPT, "switch")

    def test_existing_checkout_without_venv_is_not_cloned_again(self):
        ctl = make_shelly_control(FakeShellyHost([SHELLYSCRIPT]))
        ctl.poweron()
        assert [c[0] for c in installs(ctl)] == ["python3", SHELLYDIR + "/.venv/bin/pip"]

    def test_install_switched_off_stops(self):
        ctl = make_shelly_control(FakeShellyHost(), shelly_install=False)
        with pytest.raises(RuntimeError, match="installing it is switched off"):
            ctl.poweron()
        assert installs(ctl) == []
        assert switches(ctl) == []

    def test_install_switched_off_uses_tooldir(self):
        ctl = make_shelly_control(FakeShellyHost(INSTALLED), shelly_install=False)
        ctl.poweron()
        assert switches(ctl)[0][:2] == (SHELLYPY, SHELLYSCRIPT)

    def test_install_switched_off_uses_path(self):
        ctl = make_shelly_control(
            FakeShellyHost(commands=["shelly-ctrl.py"]), shelly_install=False
        )
        ctl.poweron()
        assert switches(ctl)[0][0] == "shelly-ctrl.py"

    def test_tooldir_can_be_set(self):
        ctl = make_shelly_control(
            FakeShellyHost(["/srv/shelly/.venv/bin/python", "/srv/shelly/shelly-ctrl.py"]),
            shelly_tooldir=ShellyPath("/srv/shelly"),
        )
        ctl.poweron()
        assert switches(ctl)[0][:2] == ("/srv/shelly/.venv/bin/python", "/srv/shelly/shelly-ctrl.py")
        assert installs(ctl) == []

    def test_optional_settings_are_passed(self):
        ctl = make_shelly_control(
            FakeShellyHost(commands=["/usr/local/bin/shelly-ctrl.py"]),
            shelly_device="DC:B4:D9:CD:25:B4",
            shelly_id="1",
            shelly_command="/usr/local/bin/shelly-ctrl.py",
            shelly_timeout="10",
        )
        ctl.poweron()
        assert switches(ctl) == [
            (
                "/usr/local/bin/shelly-ctrl.py",
                "switch",
                "DC:B4:D9:CD:25:B4",
                "on",
                "--id",
                "1",
                "-t",
                "10",
            )
        ]
        assert installs(ctl) == []

    def test_explicit_command_is_checked_once(self):
        host = FakeShellyHost(commands=["/usr/local/bin/shelly-ctrl.py"])
        for _ in range(2):
            make_shelly_control(
                host, shelly_command="/usr/local/bin/shelly-ctrl.py"
            ).poweron()
        assert lookups(host) == [("command", "-v", "/usr/local/bin/shelly-ctrl.py")]
        assert len([c for c in host.commands if "switch" in c]) == 2

    def test_missing_explicit_command_is_not_installed(self):
        ctl = make_shelly_control(
            FakeShellyHost(), shelly_command="/usr/local/bin/shelly-ctrl.py"
        )
        with pytest.raises(RuntimeError, match="not found on the lab host"):
            ctl.poweron()
        assert installs(ctl) == []
        assert switches(ctl) == []

    def test_poweroff_respects_nopoweroff_flag(self, monkeypatch):
        monkeypatch.setattr(powercontrol.time, "sleep", lambda s: None)
        ctl = make_shelly_control()
        sys.modules["tbot"].flags = {"nopoweroff"}
        ctl.poweroff()
        assert ctl.host.commands == []


def make_sispm_control(device="01:01:5c:29:39", port="2"):
    class Ctl(powercontrol.SispmControl):
        sispmctl_device = device
        sispmctl_port = port
        host = FakeExecHost()

    return Ctl()


class TestSispmControl:
    def test_poweron_calls_sispmctl_with_o_flag(self):
        ctl = make_sispm_control()
        ctl.poweron()
        assert ctl.host.commands == [
            ("sispmctl", "-D", "01:01:5c:29:39", "-o", "2")
        ]

    def test_poweroff_calls_sispmctl_with_f_flag(self, monkeypatch):
        monkeypatch.setattr(powercontrol.time, "sleep", lambda s: None)
        ctl = make_sispm_control()
        ctl.poweroff()
        assert ctl.host.commands == [
            ("sispmctl", "-D", "01:01:5c:29:39", "-f", "2")
        ]

    def test_poweroff_respects_nopoweroff_flag(self, monkeypatch):
        monkeypatch.setattr(powercontrol.time, "sleep", lambda s: None)
        ctl = make_sispm_control()
        sys.modules["tbot"].flags = {"nopoweroff"}
        ctl.poweroff()
        assert ctl.host.commands == []


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
