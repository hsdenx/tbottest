"""
Unit tests for tbottest/tc/cpu.py: generic_get_socname() against a fake
board that answers cat of the compatible files of the device tree.
"""

import os

import pytest

from conftest import load_module

cpu = load_module(
    "tbottest_tc_cpu",
    os.path.join(os.path.dirname(__file__), "..", "tbottest", "tc", "cpu.py"),
)


class FakeBoard:
    """cat of a file of files, an error for any other"""

    def __init__(self, files):
        self.files = files
        self.commands = []

    def exec0(self, *args):
        self.commands.append(args)
        if args[0] == "cat" and args[1] in self.files:
            return self.files[args[1]]
        raise RuntimeError(f"{args} failed")


@pytest.mark.parametrize(
    "files,soc",
    [
        ({"/proc/device-tree/soc@0/compatible": "fsl,imx8mp-soc\x00simple-bus\x00"}, "imx8mp"),
        # the AM335x has no soc@0 node with a compatible of its own
        ({"/proc/device-tree/compatible": "ti,am335x-bone\x00ti,am33xx\x00"}, "am335x"),
        ({"/proc/device-tree/compatible": "vendor,board\x00ti,am33xx\x00"}, "am335x"),
        ({"/proc/device-tree/compatible": "st,stm32mp157\x00"}, "not detected"),
        ({}, "not detected"),
    ],
)
def test_generic_get_socname(files, soc):
    assert cpu.generic_get_socname(FakeBoard(files)) == soc


def test_imx8mp_first():
    board = FakeBoard(
        {
            "/proc/device-tree/soc@0/compatible": "fsl,imx8mp-soc\x00",
            "/proc/device-tree/compatible": "ti,am33xx\x00",
        }
    )
    assert cpu.generic_get_socname(board) == "imx8mp"
    assert board.commands == [("cat", "/proc/device-tree/soc@0/compatible")]
