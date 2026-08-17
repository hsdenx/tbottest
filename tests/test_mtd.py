"""
Unit tests for tbottest/tc/mtd.py.

_write_random_and_verify()/_hexdump() are exec0()-driven logic,
tested against a FakeLinuxShell that records calls and returns a
per-instance canned "hexdump" output (lnx_create_random()/
lnx_compare_files() are the real tc/common.py functions, loaded via
install_real_submodule so mtd.py's own import resolves them).

lnx_mtd_nvram_reboot() additionally needs tbot.ctx.request(role,
reset=...) as a context manager (not just tbot.ctx() -- see
conftest's install_tbot_stubs docstring); a small FakeCtx is
monkeypatched in locally for that, yielding one FakeLinuxShell per
"with" block so the two acquisitions in the testcase can be given
independently controlled hexdump outputs.
"""

import contextlib
import os
import sys

import pytest

from conftest import install_fake_initconfig, install_real_submodule, load_module

install_fake_initconfig()
install_real_submodule(
    "tbottest.tc.common",
    os.path.join(os.path.dirname(__file__), "..", "tbottest", "tc", "common.py"),
)

mtd = load_module(
    "tbottest_tc_mtd",
    os.path.join(os.path.dirname(__file__), "..", "tbottest", "tc", "mtd.py"),
)


class FakeLinuxShell:
    def __init__(self, hexdump_output="AABBCCDD"):
        self.commands = []
        self.hexdump_output = hexdump_output
        self.interactive_called = False

    def exec0(self, *args):
        key = tuple(str(a) for a in args)
        self.commands.append(key)
        if key[0] == "hexdump":
            return self.hexdump_output
        return ""

    def interactive(self):
        self.interactive_called = True


class FakeCtx:
    """tbot.ctx.request(role, reset=...) as a context manager, yielding
    one queued machine per call."""

    def __init__(self, machines):
        self._machines = list(machines)

    @contextlib.contextmanager
    def request(self, role, reset=False):
        yield self._machines.pop(0)


TEST = {"bs": "1", "cnt": "4", "seek": "2"}


class TestWriteRandomAndVerify:
    def test_writes_and_dds_with_correct_offsets(self):
        lnx = FakeLinuxShell()
        mtd._write_random_and_verify(lnx, "/tmp/gnlmpf", "/dev/mtd0", TEST)

        # lnx_create_random() issues its own "dd if=/dev/urandom ..." call
        # first; only check the write-to-dev one that matters here
        write_calls = [c for c in lnx.commands if c[0] == "dd" and "of=/dev/mtd0" in c]
        assert write_calls == [
            ("dd", "if=/tmp/gnlmpf", "of=/dev/mtd0", "bs=1", "count=4", "seek=2")
        ]

    def test_matching_content_does_not_call_interactive(self):
        lnx = FakeLinuxShell(hexdump_output="AABBCCDD")
        mtd._write_random_and_verify(lnx, "/tmp/gnlmpf", "/dev/mtd0", TEST)
        assert lnx.interactive_called is False

    def test_mismatch_drops_to_interactive(self, monkeypatch):
        lnx = FakeLinuxShell()
        # make the two hexdump calls inside lnx_compare_files() differ
        outputs = iter(["AAAA", "BBBB"])
        monkeypatch.setattr(
            lnx, "exec0", lambda *a: next(outputs) if a and a[0] == "hexdump" else ""
        )
        mtd._write_random_and_verify(lnx, "/tmp/gnlmpf", "/dev/mtd0", TEST)
        assert lnx.interactive_called is True


class TestHexdump:
    def test_builds_expected_command(self):
        lnx = FakeLinuxShell(hexdump_output="DEADBEEF")
        result = mtd._hexdump(lnx, "/tmp/gnlmpf", "-s", 8)
        assert result == "DEADBEEF"
        assert lnx.commands == [
            ("hexdump", "-e", '"%03.2x"', "-s", "0", "-n", "8", "/tmp/gnlmpf")
        ]


class TestLnxMtdNvram:
    def test_tests_none_raises(self):
        lnx = FakeLinuxShell()
        with pytest.raises(RuntimeError, match="please define tests"):
            mtd.lnx_mtd_nvram(lnx, tests=None)

    def test_runs_one_write_dd_per_test_entry(self):
        lnx = FakeLinuxShell()
        mtd.lnx_mtd_nvram(lnx, dev="/dev/mtd0", tests=[TEST, TEST])
        write_calls = [c for c in lnx.commands if c[0] == "dd" and "of=/dev/mtd0" in c]
        assert len(write_calls) == 2


class TestLnxMtdNvramReboot:
    def test_tests_none_raises(self):
        with pytest.raises(RuntimeError, match="please define tests"):
            mtd.lnx_mtd_nvram_reboot(tests=None)

    def test_matching_content_after_reboot_does_not_raise(self, monkeypatch):
        lnx1 = FakeLinuxShell(hexdump_output="AABB")
        lnx2 = FakeLinuxShell(hexdump_output="AABB")
        monkeypatch.setattr(sys.modules["tbot"], "ctx", FakeCtx([lnx1, lnx2]))

        mtd.lnx_mtd_nvram_reboot(dev="/dev/mtd0", tests=[TEST])  # must not raise

        assert lnx1.interactive_called is False
        dd_calls_lnx2 = [c for c in lnx2.commands if c[0] == "dd"]
        assert dd_calls_lnx2 == [
            ("dd", "if=/dev/mtd0", "of=/tmp/gnlmpf", "bs=1", "count=4", "skip=2")
        ]

    def test_content_mismatch_after_reboot_raises(self, monkeypatch):
        lnx1 = FakeLinuxShell(hexdump_output="AABB")
        lnx2 = FakeLinuxShell(hexdump_output="CCDD")
        monkeypatch.setattr(sys.modules["tbot"], "ctx", FakeCtx([lnx1, lnx2]))

        with pytest.raises(RuntimeError, match="files have not same content"):
            mtd.lnx_mtd_nvram_reboot(dev="/dev/mtd0", tests=[TEST])
