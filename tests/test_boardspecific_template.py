"""
Unit tests for the template tbottest/tbotconfig/BOARDNAME/boardspecific.py:
the lab server IP and the board IP come from section IPSETUP_<boardname>_eth0
of tbot.ini, read with init_read_inifile() and init_section_get_config() of
tbottest/initconfig.py (loaded from there by conftest).
"""

import os
import sys
import types

import pytest

from conftest import load_initconfig_functions, load_module

TEMPLATE = os.path.join(
    os.path.dirname(__file__), "..", "tbottest", "tbotconfig", "BOARDNAME", "boardspecific.py"
)

TBOT_INI = """
[LABHOST]
serverip = 192.168.3.1

[IPSETUP_testboard_eth0]
serverip = ${LABHOST:serverip}
ipaddr = 192.168.3.20

[IPSETUP_testboard_eth1]
serverip = 10.0.0.1
ipaddr = 10.0.0.20

[IPSETUP_other_eth0]
serverip = 172.16.0.1
ipaddr = 172.16.0.20
"""


@pytest.fixture
def template(monkeypatch, tmp_path):
    ini = load_initconfig_functions(boardname="testboard")
    for name in ("replace_in_file", "find_in_file_and_delete"):
        setattr(ini, name, lambda *args: None)
    monkeypatch.setitem(sys.modules, "tbottest", types.ModuleType("tbottest"))
    monkeypatch.setitem(sys.modules, "tbottest.initconfig", ini)
    mod = load_module("tbottest_boardspecific_template", TEMPLATE)
    inifile = tmp_path / "tbot.ini"
    inifile.write_text(TBOT_INI)
    return mod, str(inifile)


def test_serverip_of_the_board_eth0(template):
    mod, inifile = template
    # interpolated like IniTBotConfig reads tbot.ini
    assert mod.BOARDNAME_get_lab_serverip(inifile) == "192.168.3.1"


def test_ipaddr_of_the_board_eth0(template):
    mod, inifile = template
    assert mod.BOARDNAME_get_board_ipaddr(inifile) == "192.168.3.20"


def test_missing_section(template, tmp_path):
    mod, _ = template
    empty = tmp_path / "empty.ini"
    empty.write_text("[IPSETUP_other_eth0]\\nipaddr = 1.2.3.4\\n")
    with pytest.raises(RuntimeError, match="ipaddr not found"):
        mod.BOARDNAME_get_board_ipaddr(str(empty))
    with pytest.raises(RuntimeError, match="serverip setup not found"):
        mod.BOARDNAME_get_lab_serverip(str(empty))
