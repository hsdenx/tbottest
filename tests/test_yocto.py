"""
Unit tests for tbottest/tc/yocto.py: reading the environment setup script
from the output of the SDK installer.
"""

import os

import pytest

from conftest import load_module

yocto = load_module(
    "tbottest_tc_yocto",
    os.path.join(os.path.dirname(__file__), "..", "tbottest", "tc", "yocto.py"),
)

INSTALL = "/work/sdk/abb-amc-musl"

# output of the installer of a core-image-minimal SDK (Wrynose), with
# the install path replaced
LOG = """ABB AMC Linux SDK installer version nodistro.0
==============================================
You are about to install the SDK to "/work/sdk/abb-amc-musl". Proceed [Y/n]? Y
Extracting SDK....................................................................done
Setting it up...done
SDK has been successfully set up and is ready to be used.
Each time you wish to use the SDK in a new shell session, you need to source the environment setup script e.g.
 $ . /work/sdk/abb-amc-musl/environment-setup-ppc8xx-abb-linux-musl
"""


class TestEnvcmdFromLog:
    def test_environment_script_found(self):
        assert yocto.yocto_sdk_envcmd_from_log(LOG, INSTALL) == (
            "/work/sdk/abb-amc-musl/environment-setup-ppc8xx-abb-linux-musl"
        )

    def test_proceed_line_is_not_taken(self):
        log = LOG.split("Extracting")[0]
        assert yocto.yocto_sdk_envcmd_from_log(log, INSTALL) is None

    def test_other_install_path(self):
        assert yocto.yocto_sdk_envcmd_from_log(LOG, "/other/path") is None

    def test_line_with_path_but_no_command(self):
        log = "Setting up /work/sdk/abb-amc-musl\n" + LOG
        assert yocto.yocto_sdk_envcmd_from_log(log, INSTALL).endswith(
            "environment-setup-ppc8xx-abb-linux-musl"
        )


class FakeShell:
    """records the commands, answers the installer call with LOG"""

    def __init__(self):
        self.calls = []

    def exec0(self, *args):
        self.calls.append(tuple(str(a) for a in args))
        if args and str(args[0]).endswith(".sh"):
            return LOG
        return ""


class TestInstallSdk:
    def test_install_dir_removed_by_absolute_path(self):
        lnx = FakeShell()
        env = yocto.check_yocto_build_install_sdk(lnx, INSTALL, "/sdk", "toolchain.sh")
        assert env == INSTALL + "/environment-setup-ppc8xx-abb-linux-musl"
        assert lnx.calls[:3] == [
            ("rm", "-rf", INSTALL),
            ("mkdir", "-p", INSTALL),
            ("/sdk/toolchain.sh", "-y", "-d", INSTALL),
        ]
        assert not any("*" in a for c in lnx.calls for a in c)
        assert yocto.check_yocto_sdk_get_scriptname() == env

    def test_relative_install_path_refused(self):
        lnx = FakeShell()
        with pytest.raises(RuntimeError, match="must be absolute"):
            yocto.check_yocto_build_install_sdk(lnx, "sdk/amc", "/sdk", "toolchain.sh")
        assert lnx.calls == []

    def test_root_refused(self):
        lnx = FakeShell()
        with pytest.raises(RuntimeError, match="must be absolute"):
            yocto.check_yocto_build_install_sdk(lnx, "/", "/sdk", "toolchain.sh")
        assert lnx.calls == []
