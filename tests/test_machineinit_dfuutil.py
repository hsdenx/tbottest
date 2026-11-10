"""
Unit tests for the dfu-util loader in tbottest/machineinit.py: a missing
file and a failed download stop the load, a download that only fails the
status request after the device left DFU mode does not.

FakeHost answers "test -f" from a set of existing files and returns a
given result for dfu-util.
"""

import os

import pytest

from conftest import load_definition

PATH = os.path.join(os.path.dirname(__file__), "..", "tbottest", "machineinit.py")

helper = load_definition("tbottest_machineinit_dfuutil_done", PATH, "dfuutil_download_done")
dfu = load_definition(
    "tbottest_machineinit_dfuutil",
    PATH,
    "DFUUTIL",
    extra_src=(
        "import abc\n"
        "import typing\n"
        "from typing import List\n"
        "import types\n"
        "machine = types.SimpleNamespace(Initializer=object)\n"
        "linux = types.SimpleNamespace(Raw=str)\n"
        "def search_string_in_multiline(s, log):\n"
        "    return s in log\n"
        "DFUUTIL_TIMEOUT = 30\n"
    ),
)
dfu.dfuutil_download_done = helper.dfuutil_download_done

DONE = "Download\t[=========================] 100%\nDownload done.\n"
STATUS_ERROR = "dfu-util: Error during download get_status\n"


class FakeHost:
    name = "lab"

    def __init__(self, files, result):
        self.files = files
        self.result = result
        self.commands = []

    def test(self, *args):
        self.commands.append(args)
        return args[-1] in self.files

    def exec(self, *args):
        self.commands.append(args)
        return self.result


def loader(host, steps):
    class Board(dfu.DFUUTIL):
        def dfuutil_loader_steps(self):
            return steps

    b = Board.__new__(Board)
    b.host = host
    return b


STEPS = [{"a": "bootloader", "D": "/tftp/tiboot3.bin"}, {"a": "tispl.bin", "D": "/tftp/tispl.bin"}]


class TestDownloadDone:
    def test_retcode_0(self):
        assert helper.dfuutil_download_done(0, "")

    def test_status_error_after_download(self):
        assert helper.dfuutil_download_done(74, DONE + STATUS_ERROR)

    def test_failed_without_download(self):
        assert not helper.dfuutil_download_done(74, "dfu-util: No DFU capable USB device available\n")


class TestLoad:
    def test_missing_file_stops_before_dfu_util(self):
        host = FakeHost({"/tftp/tispl.bin"}, (0, DONE))
        with pytest.raises(RuntimeError, match="/tftp/tiboot3.bin does not exist on lab"):
            loader(host, STEPS)._load()
        assert all(c[0] != "timeout" for c in host.commands)

    def test_failed_download_stops(self):
        nodev = "dfu-util: No DFU capable USB device available\n"
        host = FakeHost({"/tftp/tiboot3.bin", "/tftp/tispl.bin"}, (74, nodev))
        with pytest.raises(RuntimeError, match="could not download /tftp/tiboot3.bin to bootloader"):
            loader(host, STEPS)._load()

    def test_device_reset_after_download_goes_on(self):
        host = FakeHost({"/tftp/tiboot3.bin", "/tftp/tispl.bin"}, (74, DONE + STATUS_ERROR))
        loader(host, STEPS)._load()
        assert [c[:3] for c in host.commands if c[0] == "timeout"] == [
            ("timeout", "30", "dfu-util"),
            ("timeout", "30", "dfu-util"),
        ]

    def test_timeout_of_a_step(self):
        host = FakeHost({"/tftp/tiboot3.bin"}, (0, DONE))
        loader(host, [{"a": "bootloader", "D": "/tftp/tiboot3.bin", "timeout": 90}])._load()
        assert host.commands[-1][:3] == ("timeout", "90", "dfu-util")

    def test_board_not_in_dfu_mode_stops(self):
        waiting = "dfu-util: Cannot open DFU device 04f2:b6be found on devnum 3 (LIBUSB_ERROR_ACCESS)\n"
        host = FakeHost({"/tftp/tiboot3.bin", "/tftp/tispl.bin"}, (124, waiting * 20))
        with pytest.raises(RuntimeError, match="did not load /tftp/tiboot3.bin within 30 s"):
            loader(host, STEPS)._load()
