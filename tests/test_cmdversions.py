"""
Unit tests for tbottest/cmdversions.py: the ini key cmd_versions, which
package manager a system has, the install commands, and the mixin that
gives the generic machines the ini preset and install_package().
"""

import configparser
import os
import sys

import pytest

from conftest import install_fake_initconfig, install_real_submodule, load_module

install_fake_initconfig()
install_real_submodule(
    "tbottest.tc.common",
    os.path.join(os.path.dirname(__file__), "..", "tbottest", "tc", "common.py"),
)
cmdversions = load_module(
    "tbottest_cmdversions",
    os.path.join(os.path.dirname(__file__), "..", "tbottest", "cmdversions.py"),
)

FEDORA = 'NAME=Fedora\nVERSION="33 (Workstation Edition)"\nID=fedora\nVERSION_ID=33\n'
DEBIAN = 'PRETTY_NAME="Debian GNU/Linux 12 (bookworm)"\nID=debian\nVERSION_ID="12"\n'
UBUNTU = "NAME=Ubuntu\nID=ubuntu\nID_LIKE=debian\n"
CENTOS = 'NAME="CentOS Stream"\nID="centos"\nID_LIKE="rhel fedora"\n'
YOCTO = 'ID=poky\nNAME="Poky (Yocto Project Reference Distro)"\nVERSION_ID=5.0\n'


class TestFromConfig:
    @pytest.mark.parametrize("value", [None, "", "  ", "None"])
    def test_empty(self, value):
        assert cmdversions.cmd_versions_from_config(value) == {}

    def test_dictionary(self):
        value = '{"top": "busybox:1.37.0", "ps": "procps-ng:4.0.6"}'
        assert cmdversions.cmd_versions_from_config(value) == {
            "top": "busybox:1.37.0",
            "ps": "procps-ng:4.0.6",
        }

    def test_one_command_per_line(self):
        versions = {"top": "busybox:1.37.0", "devmem2": "notfound"}
        assert cmdversions.cmd_versions_to_config(versions) == (
            "cmd_versions = {\n"
            '    "top": "busybox:1.37.0",\n'
            '    "devmem2": "notfound",\n'
            "    }"
        )

    @pytest.mark.parametrize("keyindent", ["", "    "])
    def test_round_trip_through_configparser(self, keyindent):
        versions = {"top": "busybox:1.37.0", "devmem2": "notfound"}
        ini = "[TC]\n" + keyindent + "tmpdir = /tmp\n"
        ini += cmdversions.cmd_versions_to_config(versions, keyindent) + "\n"
        ini += keyindent + "testdir = /tmp/t\n"
        cp = configparser.RawConfigParser()
        cp.read_string(ini)
        assert cmdversions.cmd_versions_from_config(cp.get("TC", "cmd_versions")) == versions
        assert cp.get("TC", "testdir") == "/tmp/t"

    def test_no_dictionary(self):
        with pytest.raises(ValueError, match="no dictionary"):
            cmdversions.cmd_versions_from_config('["top"]')


class TestOsReleaseFamily:
    @pytest.mark.parametrize(
        "osrelease,family",
        [(FEDORA, "fedora"), (DEBIAN, "debian"), (UBUNTU, "debian"), (CENTOS, "fedora"), (YOCTO, "")],
    )
    def test_family(self, osrelease, family):
        assert cmdversions.os_release_family(osrelease) == family

    def test_name_does_not_count(self):
        # only ID and ID_LIKE, not NAME or PRETTY_NAME
        assert cmdversions.os_release_family('NAME="not debian"\nID=foo\n') == ""


class TestInstallCommands:
    def test_debian_package_with_other_name(self):
        assert cmdversions.install_commands("debian", "hexdump") == [
            ["apt-get", "-y", "install", "bsdextrautils"]
        ]

    def test_debian_package_with_command_name(self):
        assert cmdversions.install_commands("debian", "iperf3") == [
            ["apt-get", "-y", "install", "iperf3"]
        ]

    def test_fedora_file_provides(self):
        assert cmdversions.install_commands("fedora", "ifconfig") == [
            ["dnf", "-y", "install", "/usr/bin/ifconfig"],
            ["dnf", "-y", "install", "/usr/sbin/ifconfig"],
        ]

    def test_unknown_system(self):
        assert cmdversions.install_commands("", "top") == []


class FakeShell:
    """answers cat /etc/os-release and id -u; install commands whose
    last argument is in fail return 1"""

    def __init__(self, osrelease, uid="0", name="cmdversions-lab", fail=()):
        self.osrelease = osrelease
        self.uid = uid
        self.name = name
        self.fail = set(fail)
        self.calls = []

    def exec0(self, *args):
        self.calls.append(args)
        return f"{self.uid}\n" if args == ("id", "-u") else ""

    def exec(self, *args):
        self.calls.append(args)
        if args == ("cat", "/etc/os-release"):
            return (0, self.osrelease)
        return (1 if args[-1] in self.fail else 0, "")

    def installs(self):
        return [c for c in self.calls if c not in (("cat", "/etc/os-release"), ("id", "-u"))]


@pytest.fixture(autouse=True)
def fresh_uid_cache():
    # install_package() imports tbottest.tc.common when called; other test
    # files may have put another module object there
    uid = sys.modules["tbottest.tc.common"]._UID
    uid.clear()
    yield
    uid.clear()


class TestInstallPackage:
    def test_fedora_tries_sbin_after_bin(self):
        lnx = FakeShell(FEDORA, fail={"/usr/bin/ifconfig"})
        assert cmdversions.install_package(lnx, "ifconfig") is True
        assert lnx.installs() == [
            ("dnf", "-y", "install", "/usr/bin/ifconfig"),
            ("dnf", "-y", "install", "/usr/sbin/ifconfig"),
        ]

    def test_debian_as_user_with_sudo(self):
        lnx = FakeShell(UBUNTU, uid="1000")
        assert cmdversions.install_package(lnx, "top") is True
        assert lnx.installs() == [("sudo", "apt-get", "-y", "install", "procps")]

    def test_failed_install(self):
        lnx = FakeShell(DEBIAN, fail={"iperf3"})
        assert cmdversions.install_package(lnx, "iperf3") is False

    def test_yocto_installs_nothing(self):
        lnx = FakeShell(YOCTO)
        assert cmdversions.install_package(lnx, "top") is False
        assert lnx.installs() == []


class FakeLinuxShell:
    """the cmd_get_version() part of LinuxShell of tbot"""

    def __init__(self):
        self.versions = {}
        self.found_out = []

    def cmd_versions_set(self, versions):
        self.versions.update(versions)

    def install_package(self, cmd):
        return False

    def cmd_get_version(self, cmd, autoinstall=False, refresh=False):
        if refresh or cmd not in self.versions:
            self.found_out.append(cmd)
            self.versions[cmd] = "notfound"
        return self.versions[cmd]


class Machine(cmdversions.CmdVersionsMixin, FakeLinuxShell):
    cmd_versions_config = '{"top": "busybox:1.37.0", "ps": "procps-ng:4.0.6"}'


class TestMixin:
    def test_preset_from_config(self):
        m = Machine()
        assert m.cmd_get_version("top") == "busybox:1.37.0"
        assert m.found_out == []

    def test_not_preset_is_found_out(self):
        m = Machine()
        assert m.cmd_get_version("devmem") == "notfound"
        assert m.found_out == ["devmem"]

    def test_testcase_value_wins_over_config(self):
        m = Machine()
        m.cmd_versions_set({"top": "procps-ng:3.3.16"})
        assert m.cmd_get_version("top") == "procps-ng:3.3.16"
        assert m.cmd_get_version("ps") == "procps-ng:4.0.6"

    def test_config_applied_once(self):
        m = Machine()
        m.cmd_get_version("top")
        m.versions["top"] = "busybox:1.36.1"
        assert m.cmd_get_version("top") == "busybox:1.36.1"

    def test_refresh_passed_on(self):
        m = Machine()
        assert m.cmd_get_version("top", refresh=True) == "notfound"
        assert m.found_out == ["top"]

    def test_without_config(self):
        class Plain(cmdversions.CmdVersionsMixin, FakeLinuxShell):
            pass

        assert Plain().cmd_get_version("top") == "notfound"

    def test_install_package(self, monkeypatch):
        asked = []
        monkeypatch.setattr(
            cmdversions, "install_package", lambda lnx, cmd: asked.append(cmd) or True
        )
        assert Machine().install_package("iperf3") is True
        assert asked == ["iperf3"]


class TestLnxCmdVersions:
    """the testcase lnx_cmd_versions in tbottest/tc/common.py"""

    class Shell:
        def __init__(self, impls):
            self.impls = impls
            self.asked = []

        def cmd_get_version(self, cmd, autoinstall=False, refresh=False):
            self.asked.append((cmd, autoinstall, refresh))
            return self.impls.get(cmd, "notfound")

    @pytest.fixture(autouse=True)
    def real_cmdversions(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "tbottest.cmdversions", cmdversions)

    def test_logs_one_command_per_line(self, monkeypatch):
        import tbot

        logged = []
        monkeypatch.setattr(tbot.log, "message", logged.append, raising=False)
        common = sys.modules["tbottest.tc.common"]
        common.lnx_cmd_versions(self.Shell({"top": "busybox:1.37.0"}), ["top"], keyindent="    ")
        assert logged == ['    cmd_versions = {\n        "top": "busybox:1.37.0",\n        }']

    def test_given_commands_asked_again(self):
        lnx = self.Shell({"top": "busybox:1.37.0"})
        common = sys.modules["tbottest.tc.common"]
        assert common.lnx_cmd_versions(lnx, ["top", "devmem2"], autoinstall=True) == {
            "top": "busybox:1.37.0",
            "devmem2": "notfound",
        }
        assert lnx.asked == [("top", True, True), ("devmem2", True, True)]

    def test_default_commands(self):
        lnx = self.Shell({})
        common = sys.modules["tbottest.tc.common"]
        versions = common.lnx_cmd_versions(lnx)
        assert list(versions) == cmdversions.TBOTTEST_COMMANDS
