"""
Additional unit tests for tbottest/tc/common.py, covering functions
not already exercised by tests/test_common.py (search_*/_poll_until)
or indirectly via tests/test_can.py, test_mtd.py, test_rs485.py
(lnx_create_random, lnx_compare_files, tbot_copy_file_to_board,
tbot_start_thread/tbot_stop_thread).

Focus is on: the bugs fixed in this pass (each with a regression
test reproduced against the pre-fix code first, see conversation
history) and the pure-logic parsers (escape_ansi, lx_devmem2_get,
lnx_get_hwaddr, _lnx_get_ipaddr/lnx_get_ipaddr, lnx_check_cmd,
ub_check_i2c_dump). tbot.ctx()-based functions (board_wait_for_device,
board_ub_delete_env, board_set_default) use a small FakeCtx matching
common.py's usage shape: `with tbot.ctx() as cx: cx.request(role)`
(unlike rs485.py/mtd.py, which call tbot.ctx.request(role) directly).
"""

import contextlib
import os
import sys
import tempfile

import pytest

from conftest import install_fake_initconfig, load_module

install_fake_initconfig()

common = load_module(
    "tbottest_tc_common_more",
    os.path.join(os.path.dirname(__file__), "..", "tbottest", "tc", "common.py"),
)


class FakeLinuxShell:
    def __init__(self):
        self.commands = []
        self.responses = {}

    def _respond(self, key):
        for prefix, out in self.responses.items():
            if key[: len(prefix)] == prefix:
                return out
        return ""

    def exec0(self, *args):
        key = tuple(str(a) for a in args)
        self.commands.append(key)
        return self._respond(key)

    def exec(self, *args):
        key = tuple(str(a) for a in args)
        self.commands.append(key)
        return (0, self._respond(key))


class FakeCtxHandle:
    def __init__(self, machine):
        self._machine = machine

    def request(self, role):
        return self._machine


class FakeCtx:
    """Matches common.py's `with tbot.ctx() as cx: cx.request(role)`
    usage: tbot.ctx() itself is the context manager, cx.request()
    returns the machine directly (no further "with")."""

    def __init__(self, machine):
        self._machine = machine

    @contextlib.contextmanager
    def __call__(self):
        yield FakeCtxHandle(self._machine)


class TestEscapeAnsi:
    def test_strips_ansi_codes(self):
        assert common.escape_ansi("\x1b[31mred\x1b[0m") == "red"

    def test_leaves_plain_text_unchanged(self):
        assert common.escape_ansi("plain text") == "plain text"


class TestLxDevmem2Get:
    def test_parses_value_at_address_format(self):
        lnx = FakeLinuxShell()
        lnx.responses[("devmem2",)] = "Value at address 0x1000 (0x1000): 0x12345678"
        assert common.lx_devmem2_get(lnx, "0x1000", "w") == "0x12345678"

    def test_parses_read_at_address_format(self):
        lnx = FakeLinuxShell()
        lnx.responses[("devmem2",)] = "Read at address 0x1000 (0x1000): 0xAABBCCDD"
        assert common.lx_devmem2_get(lnx, "0x1000", "w") == "0xAABBCCDD"

    def test_unexpected_output_raises(self):
        lnx = FakeLinuxShell()
        lnx.responses[("devmem2",)] = "garbage output"
        with pytest.raises(RuntimeError, match="unexpected output"):
            common.lx_devmem2_get(lnx, "0x1000", "w")


class TestLnxCheckRevfile:
    def _revfile(self, content):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".rev", delete=False)
        f.write(content)
        f.close()
        return f.name

    def test_blank_line_does_not_crash(self):
        """
        Regression test: cols = line.split() on a blank line gives [],
        and cols[0] used to raise IndexError before checking whether
        the line was a comment/blank.
        """
        revfile = self._revfile("0x1000 0xffffffff w 0x0\n\n0x2000 0xffffffff w 0x0\n")
        lnx = FakeLinuxShell()
        lnx.responses[("command",)] = ""  # lx_cmd_exists: devmem2 exists
        lnx.responses[("devmem2",)] = "Value at address 0x1000 (0x1000): 0x00000000"
        try:
            assert common.lnx_check_revfile(lnx, revfile) is True
        finally:
            os.unlink(revfile)

    def test_comment_line_skipped(self):
        revfile = self._revfile("# a comment\n0x1000 0xffffffff w 0x0\n")
        lnx = FakeLinuxShell()
        lnx.responses[("command",)] = ""
        lnx.responses[("devmem2",)] = "Value at address 0x1000 (0x1000): 0x00000000"
        try:
            assert common.lnx_check_revfile(lnx, revfile) is True
        finally:
            os.unlink(revfile)

    def test_mismatch_returns_false(self):
        revfile = self._revfile("0x1000 0xffffffff w 0x0\n")
        lnx = FakeLinuxShell()
        lnx.responses[("command",)] = ""
        lnx.responses[("devmem2",)] = "Value at address 0x1000 (0x1000): 0xffffffff"
        try:
            assert common.lnx_check_revfile(lnx, revfile) is False
        finally:
            os.unlink(revfile)

    def test_devmem2_missing_returns_none(self):
        revfile = self._revfile("0x1000 0xffffffff w 0x0\n")
        lnx = FakeLinuxShell()
        lnx.responses[("command",)] = "command not found"

        class NotFoundHost(FakeLinuxShell):
            def exec(self, *args):
                self.commands.append(tuple(str(a) for a in args))
                return (1, "")

        lnx = NotFoundHost()
        try:
            assert common.lnx_check_revfile(lnx, revfile) is None
        finally:
            os.unlink(revfile)


class TestLnxCreateRevfile:
    def test_unsupported_readtype_raises(self):
        """
        Regression test: an unrecognized readtype used to leave
        `step` unassigned (only if/if/if, no else), raising a
        confusing NameError once the loop tried to use it.
        """
        lnx = FakeLinuxShell()
        lnx.responses[("command",)] = ""
        lnx.responses[("uname",)] = "Linux somehost 5.10.0"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".rev", delete=False) as f:
            revfile = f.name
        try:
            with pytest.raises(RuntimeError, match="readtype x not supported"):
                common.lnx_create_revfile(lnx, revfile, "0x1000", "0x1010", readtype="x")
        finally:
            os.unlink(revfile)

    @pytest.mark.parametrize("readtype,expected_step", [("w", 4), ("h", 2), ("b", 1)])
    def test_supported_readtypes_use_correct_step(self, readtype, expected_step):
        lnx = FakeLinuxShell()
        lnx.responses[("command",)] = ""
        lnx.responses[("uname",)] = "Linux somehost 5.10.0"
        lnx.responses[("devmem2",)] = "Value at address 0x1000 (0x1000): 0x0"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".rev", delete=False) as f:
            revfile = f.name
        try:
            common.lnx_create_revfile(
                lnx, revfile, "0x1000", hex(0x1000 + expected_step * 2), readtype=readtype
            )
            devmem_calls = [c for c in lnx.commands if c[0] == "devmem2"]
            assert len(devmem_calls) == 2
        finally:
            os.unlink(revfile)


class TestLnxGetHwaddr:
    def test_parses_hwaddr(self):
        lnx = FakeLinuxShell()
        lnx.responses[("ifconfig",)] = "eth0 Link encap:Ethernet HWaddr 00:11:22:33:44:55"
        assert common.lnx_get_hwaddr(lnx, "eth0") == "00:11:22:33:44:55"

    def test_missing_hwaddr_raises(self):
        lnx = FakeLinuxShell()
        lnx.responses[("ifconfig",)] = "eth0 Link encap:Ethernet"
        with pytest.raises(RuntimeError, match="Could not get hwaddr"):
            common.lnx_get_hwaddr(lnx, "eth0")


class TestLnxGetIpaddr:
    def test_parses_ipv4(self):
        lnx = FakeLinuxShell()
        lnx.responses[("ifconfig",)] = "eth0\n          inet addr:10.0.0.5  Bcast:10.0.0.255"
        assert common._lnx_get_ipaddr(lnx, "eth0") == "10.0.0.5"

    def test_parses_ipv6(self):
        """
        Note: the ip6 regex ("\\d+.\\d+.\\d+.\\d+") only matches
        decimal-digit groups, so it can never actually match a real
        IPv6 address (hex letters, "::" compression) -- this is a
        pre-existing issue, not something introduced or fixed in this
        pass (unclear what a correct general replacement should be
        without real target `ifconfig` output to validate against),
        so this test documents current behavior against a
        (unrealistic) all-digit address rather than a real one.
        """
        lnx = FakeLinuxShell()
        lnx.responses[("ifconfig",)] = "eth0\n          inet6 addr:1.2.3.4  Scope:Link"
        assert common._lnx_get_ipaddr(lnx, "eth0", ip6=True) == "1.2.3.4"

    def test_polls_until_ip_appears(self, monkeypatch):
        monkeypatch.setattr(common.time, "sleep", lambda s: None)
        calls = {"n": 0}

        class FlakyHost(FakeLinuxShell):
            def exec0(self, *args):
                calls["n"] += 1
                if calls["n"] < 3:
                    return "eth0"
                return "eth0\n          inet addr:10.0.0.5  Bcast:10.0.0.255"

        lnx = FlakyHost()
        assert common.lnx_get_ipaddr(lnx, "eth0", poll=5, sleep=0) == "10.0.0.5"

    def test_gives_up_after_poll_attempts(self, monkeypatch):
        monkeypatch.setattr(common.time, "sleep", lambda s: None)
        lnx = FakeLinuxShell()
        lnx.responses[("ifconfig",)] = "eth0"
        with pytest.raises(RuntimeError, match="Could not get ip"):
            common.lnx_get_ipaddr(lnx, "eth0", poll=2, sleep=0)


class TestLnxCheckCmd:
    def test_all_commands_pass(self):
        lnx = FakeLinuxShell()
        lnx.responses[("uname",)] = "Linux 5.10.0"
        cmd_dict = [{"cmd": "uname -a", "val": "5.10.0"}]

        class RawHost(FakeLinuxShell):
            def exec0(self, *args):
                self.commands.append(tuple(str(a) for a in args))
                return "Linux 5.10.0"

        assert common.lnx_check_cmd(RawHost(), cmd_dict) is True

    def test_undef_skips_value_check(self):
        class RawHost(FakeLinuxShell):
            def exec0(self, *args):
                self.commands.append(tuple(str(a) for a in args))
                return "anything"

        cmd_dict = [{"cmd": "true", "val": "undef"}]
        assert common.lnx_check_cmd(RawHost(), cmd_dict) is True

    def test_missing_value_raises(self):
        class RawHost(FakeLinuxShell):
            def exec0(self, *args):
                self.commands.append(tuple(str(a) for a in args))
                return "unrelated output"

        cmd_dict = [{"cmd": "uname -a", "val": "5.10.0"}]
        with pytest.raises(RuntimeError, match="not found in"):
            common.lnx_check_cmd(RawHost(), cmd_dict)


class TestLnxInstallPackage:
    def test_debian_uses_apt(self):
        lnx = FakeLinuxShell()
        lnx.responses[("cat",)] = "ID=debian"
        common.lnx_install_package(lnx, "somepkg")
        assert ("sudo", "apt-get", "-y", "install", "somepkg") in lnx.commands

    def test_fedora_uses_dnf(self):
        """
        Regression test: the Fedora branch called
        common_install_debian() (copy-paste from the branch above it)
        instead of common_install_fedora(), so a Fedora target would
        get an apt-get command instead of dnf.
        """
        lnx = FakeLinuxShell()
        lnx.responses[("cat",)] = "NAME=Fedora"
        common.lnx_install_package(lnx, "somepkg")
        assert ("sudo", "dnf", "-y", "install", "somepkg") in lnx.commands
        assert not any(c[:2] == ("sudo", "apt-get") for c in lnx.commands)

    def test_unsupported_os_raises(self):
        lnx = FakeLinuxShell()
        lnx.responses[("cat",)] = "ID=arch"
        with pytest.raises(RuntimeError, match="not supported yet"):
            common.lnx_install_package(lnx, "somepkg")


class TestBoardMtdpartsRequired:
    def test_board_ub_delete_env_default_mtdparts_raises_clearly(self):
        """
        Regression test: the default mtdparts=["env", "env-red"] was a
        list of *strings*, but the loop body does p["name"]/p["size"]
        assuming dicts -- calling with no mtdparts argument at all
        used to always crash with a confusing TypeError. Now requires
        it explicitly, same as the other "please configure" params in
        this file.
        """
        with pytest.raises(RuntimeError, match="please configure mtdparts"):
            common.board_ub_delete_env(FakeLinuxShell())

    def test_explicit_mtdparts_still_works(self):
        sys.modules["tbot"].ctx = FakeCtx(FakeLinuxShell())
        ub = FakeLinuxShell()
        common.board_ub_delete_env(ub, mtdparts=[{"name": "env", "size": "10000"}])
        assert ("sf", "erase", "env", "10000") in ub.commands


class TestBoardWaitForDevice:
    def test_lnx_none_still_usable_inside_check(self, monkeypatch):
        """
        Regression test: "with tbot.ctx() as cx: if lnx is None: lnx =
        cx.request(...)" was mis-indented so the with-block (and thus
        the acquired machine's lifetime) ended right after acquiring
        lnx, before check()/_poll_until() ever used it -- see
        FakeCtx below, which marks the machine "torn down" once the
        outer "with tbot.ctx()" block exits, same as a real machine's
        __exit__ would.
        """
        monkeypatch.setattr(common.time, "sleep", lambda s: None)

        class TearDownTrackingLnx(FakeLinuxShell):
            def __init__(self):
                super().__init__()
                self.torn_down = False

            def exec(self, *args):
                if self.torn_down:
                    raise RuntimeError("used after teardown")
                return super().exec(*args)

        lnx = TearDownTrackingLnx()
        lnx.responses[("ls",)] = ""

        @contextlib.contextmanager
        def fake_ctx_call():
            handle = FakeCtxHandle(lnx)
            try:
                yield handle
            finally:
                lnx.torn_down = True

        class FakeCtxWithTeardown:
            def __call__(self):
                return fake_ctx_call()

        sys.modules["tbot"].ctx = FakeCtxWithTeardown()

        common.board_wait_for_device(None, "/dev/ttyUSB0", retries=1, retry_timeout=0)


class TestLnxCreateFile:
    def test_writes_each_line(self):
        lnx = FakeLinuxShell()
        common.lnx_create_file(lnx, "/tmp/x.sh", ["line1", "line2"])
        assert lnx.commands == [
            ("echo", "line1", ">", "/tmp/x.sh"),
            ("echo", "line2", ">>", "/tmp/x.sh"),
        ]

    def test_no_filename_raises(self):
        with pytest.raises(RuntimeError, match="valid filename"):
            common.lnx_create_file(FakeLinuxShell(), None, ["x"])

    def test_default_filedata_is_empty(self):
        lnx = FakeLinuxShell()
        common.lnx_create_file(lnx, "/tmp/x.sh")
        assert lnx.commands == []


class TestSudoSubshell:
    def test_empty_cmds_returns_empty_list(self):
        assert common.sudo_subshell(FakeLinuxShell(), cmds=None) == []

    def test_password_path_writes_askpass_script_without_logging_it(self):
        """
        Regression test: this used to build the askpass script via
        linux.Raw(f'echo "...{password}..." > {tmpfile}') (breaks on
        a password containing a quote) and then `cat`ed the file,
        putting the plaintext password into the log. Now reuses
        lnx_create_file() (safe separate-args exec0) and doesn't cat.
        """

        class SubshellHost(FakeLinuxShell):
            @contextlib.contextmanager
            def subshell(self, *args):
                yield FakeLinuxShell()

        lnx = SubshellHost()
        common.sudo_subshell(lnx, cmds=["true"], password="s3cr3t")

        assert not any(c[0] == "cat" for c in lnx.commands)
        echo_calls = [c for c in lnx.commands if c[0] == "echo"]
        assert ("echo", "echo s3cr3t", ">>", "/tmp/sendpass.sh") in echo_calls


class TestUbCheckI2cDump:
    def test_matching_dump_returns_true(self):
        class Ub(FakeLinuxShell):
            def exec0(self, *args):
                self.commands.append(tuple(str(a) for a in args))
                if args[0] == "i2c" and args[1] == "md":
                    return "00: 11"
                return ""

        ub = Ub()
        assert common.ub_check_i2c_dump(ub, "0", "0x50", ["0x00: 11"]) is True

    def test_mismatch_returns_false(self):
        class Ub(FakeLinuxShell):
            def exec0(self, *args):
                self.commands.append(tuple(str(a) for a in args))
                if args[0] == "i2c" and args[1] == "md":
                    return "00: ff"
                return ""

        ub = Ub()
        assert common.ub_check_i2c_dump(ub, "0", "0x50", ["0x00: 11"]) is False

    def test_xx_marker_is_ignored(self):
        class Ub(FakeLinuxShell):
            def exec0(self, *args):
                self.commands.append(tuple(str(a) for a in args))
                if args[0] == "i2c" and args[1] == "md":
                    return "00: 11"
                return ""

        ub = Ub()
        # "xx" bytes should be skipped, never queried
        assert common.ub_check_i2c_dump(ub, "0", "0x50", ["0x00: xx 11"]) is True
        md_calls = [c for c in ub.commands if c[0] == "i2c" and c[1] == "md"]
        assert len(md_calls) == 1


class TestGenericMachineDump:
    def test_linux_dump_writes_addr_value_pairs(self, tmp_path):
        lnx = FakeLinuxShell()
        lnx.responses[("devmem2",)] = "Value at address 0x1000 (0x1000): 0xdeadbeef"
        outfile = tmp_path / "dump.txt"
        common.generic_machine_dump("linux", lnx, "0x1000", "0x1008", 4, [], str(outfile))
        content = outfile.read_text()
        assert "0x1000" in content
        assert "0xdeadbeef" in content

    def test_gap_substitutes_address(self, tmp_path):
        lnx = FakeLinuxShell()
        lnx.responses[("devmem2",)] = "Value at address 0x2000 (0x2000): 0x11111111"
        outfile = tmp_path / "dump.txt"
        gaps = [{"iaddr": "0x1000", "naddr": "0x2000"}]
        common.generic_machine_dump("linux", lnx, "0x1000", "0x1004", 4, gaps, str(outfile))
        content = outfile.read_text()
        # the gap redirected the read to 0x2000, not 0x1000
        assert "0x2000" in content
        devmem_calls = [c for c in lnx.commands if c[0] == "devmem2"]
        assert devmem_calls[0][1] == "0x2000"

    def test_unsupported_type_raises(self, tmp_path):
        outfile = tmp_path / "dump.txt"
        with pytest.raises(RuntimeError, match="not supported"):
            common.generic_machine_dump("bogus", FakeLinuxShell(), "0x0", "0x4", 4, [], str(outfile))


class TestGenericMachineDumpWrite:
    def test_uboot_writes_each_value(self, tmp_path):
        dumpfile = tmp_path / "dump.txt"
        dumpfile.write_text("0x1000     0xdeadbeef\n0x1004     0x0\n")
        ub = FakeLinuxShell()
        common.generic_machine_dump_write("u-boot", ub, str(dumpfile))
        mw_calls = [c for c in ub.commands if c[0] == "mw"]
        assert mw_calls == [
            ("mw", "0x1000", "0xdeadbeef", "1"),
            ("mw", "0x1004", "0x0", "1"),
        ]

    def test_linux_type_raises(self, tmp_path):
        dumpfile = tmp_path / "dump.txt"
        dumpfile.write_text("0x1000     0xdeadbeef\n")
        with pytest.raises(RuntimeError, match="not supported"):
            common.generic_machine_dump_write("linux", FakeLinuxShell(), str(dumpfile))
