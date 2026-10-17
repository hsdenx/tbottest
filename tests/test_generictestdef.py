"""
Unit tests for tbottest/tc/generictestdef.py: tc_config(), require_cfg()
and cfg_is_set(), with the real lookup functions of
tbottest/initconfig.py (see conftest.load_initconfig_functions()).
"""

import configparser
import os
import sys
import types

import pytest

from conftest import load_initconfig_functions, load_module

GENERICTESTDEF_PATH = os.path.join(
    os.path.dirname(__file__), "..", "tbottest", "tc", "generictestdef.py"
)

SECTIONS = {
    "TC_BOARDNAME.generic_lnx_test_dmesg": {"dmesg": "['Linux version']"},
    "TC": {"dmesg": "[]", "leds": "[]"},
}


@pytest.fixture
def gtd(monkeypatch):
    ini = load_initconfig_functions(boardname="BOARDNAME")
    cp = configparser.RawConfigParser()
    cp.read_dict(SECTIONS)

    class IniConfig:
        def get_config(self, name, default):
            return ini.init_get_config(cp, name, default)

    ini_mod = types.ModuleType("tbottest.initconfig")
    ini_mod.init_testcase = ini.init_testcase
    ini_mod.IniConfig = IniConfig
    monkeypatch.setitem(sys.modules, "tbottest", types.ModuleType("tbottest"))
    monkeypatch.setitem(sys.modules, "tbottest.initconfig", ini_mod)
    mod = load_module("tbottest_tc_generictestdef", GENERICTESTDEF_PATH)
    mod.ini_funcs = ini
    return mod


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, False),
        ("", False),
        ("[]", False),
        ("{}", False),
        ("0", False),
        ("False", False),
        ("['a']", True),
        ("eth0", True),
        ("1", True),
    ],
)
def test_cfg_is_set(gtd, value, expected):
    assert gtd.cfg_is_set(value) is expected


def test_tc_config_sets_the_testcase(gtd):
    @gtd.tc_config
    def my_testcase():
        return gtd.ini_funcs.init_current_testcase()

    assert my_testcase() == "my_testcase"
    assert gtd.ini_funcs.init_current_testcase() is None


def test_require_cfg_uses_the_testcase_section(gtd):
    calls = []

    @gtd.require_cfg("dmesg")
    def generic_lnx_test_dmesg():
        calls.append(gtd.ini_funcs.init_current_testcase())
        return "ran"

    assert generic_lnx_test_dmesg() == "ran"
    assert calls == ["generic_lnx_test_dmesg"]


def test_require_cfg_skips_without_value(gtd):
    @gtd.require_cfg("dmesg")
    def other_testcase():
        raise AssertionError("must not run")

    assert other_testcase() == gtd.TC_SKIP
    assert gtd.ini_funcs.init_current_testcase() is None


def test_require_cfg_missing_key(gtd):
    @gtd.require_cfg("nokey", msg="nokey missing")
    def tc():
        raise AssertionError("must not run")

    assert tc() == gtd.TC_SKIP
