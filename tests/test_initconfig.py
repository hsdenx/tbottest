"""
Unit tests for the _Singleton metaclass in tbottest/initconfig.py.

IniTBotConfig/IniConfig themselves can't be constructed here (their
class bodies resolve a real board environment at import time), so
these tests extract _Singleton's actual, current source out of
initconfig.py (see conftest.load_definition) and exercise it against
small throwaway classes -- which is exactly how IniTBotConfig/
IniConfig use it.
"""

import gc
import os

import pytest

from conftest import load_definition

INITCONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "tbottest", "initconfig.py"
)

initconfig = load_definition(
    "tbottest_initconfig_singleton_metaclass_only",
    INITCONFIG_PATH,
    "_Singleton",
    extra_src="import typing",
)


class TestSingleton:
    def test_repeated_construction_returns_identical_instance(self):
        class Cfg(metaclass=initconfig._Singleton):
            def __init__(self):
                self.value = object()

        a = Cfg()
        b = Cfg()
        assert a is b

    def test_init_runs_exactly_once(self):
        calls = []

        class Cfg(metaclass=initconfig._Singleton):
            def __init__(self):
                calls.append(1)

        for _ in range(5):
            Cfg()
        assert len(calls) == 1

    def test_different_classes_get_independent_singletons(self):
        class A(metaclass=initconfig._Singleton):
            pass

        class B(metaclass=initconfig._Singleton):
            pass

        assert A() is A()
        assert B() is B()
        assert A() is not B()

    def test_repeated_calls_do_not_leak_instances(self):
        """
        Regression test for the bug that motivated the singleton:
        with the old weakref.finalize(self, self.cleanup) pattern
        (a bound method holding a strong ref back to self), every
        call created a new, never-collected instance. With the
        singleton, repeated calls must not accumulate live objects.
        """

        class Cfg(metaclass=initconfig._Singleton):
            pass

        gc.collect()
        before = sum(1 for o in gc.get_objects() if isinstance(o, Cfg))
        for _ in range(50):
            Cfg()
        gc.collect()
        after = sum(1 for o in gc.get_objects() if isinstance(o, Cfg))
        assert after - before == 1


def load_get_boardname(board_set_boardname=None):
    mod = load_definition(
        "tbottest_initconfig_generic_get_boardname_only",
        INITCONFIG_PATH,
        "generic_get_boardname",
        extra_src="import tbot\nBOARDNAME = None\nboard_set_boardname = None",
    )
    mod.board_set_boardname = board_set_boardname
    return mod


class TestGenericGetBoardname:
    def test_boardname_flag(self):
        import tbot

        tbot.flags = {"do_power", "boardname:foo"}
        assert load_get_boardname().generic_get_boardname() == "foo"

    def test_old_selectableboardname_flag_is_not_taken(self):
        import tbot

        tbot.flags = {"selectableboardname:foo"}
        with pytest.raises(RuntimeError, match="-f boardname:<NAME>"):
            load_get_boardname().generic_get_boardname()

    def test_no_flag(self):
        with pytest.raises(RuntimeError, match="-f boardname:<NAME>"):
            load_get_boardname().generic_get_boardname()

    def test_board_set_boardname_wins(self):
        import tbot

        tbot.flags = {"boardname:foo"}
        mod = load_get_boardname(lambda: "bar")
        assert mod.generic_get_boardname() == "bar"

    def test_value_is_cached(self):
        import tbot

        tbot.flags = {"boardname:foo"}
        mod = load_get_boardname()
        assert mod.generic_get_boardname() == "foo"
        tbot.flags = {"boardname:other"}
        assert mod.generic_get_boardname() == "foo"


def load_poweron_cmds():
    return load_definition(
        "tbottest_initconfig_bdi2000_poweron_cmds_only",
        INITCONFIG_PATH,
        "bdi2000_poweron_cmds",
        extra_src="import tbot",
    )


CMDS = {
    "default": ["reset run"],
    "nowdt": ["reset", "go 0x40000100"],
}


class TestBdi2000PoweronCmds:
    def test_list_without_flag(self):
        assert load_poweron_cmds().bdi2000_poweron_cmds(["reset run"]) == [
            "reset run"
        ]

    def test_list_with_none_flag(self):
        import tbot

        tbot.flags = {"poweron_cmds:None"}
        assert load_poweron_cmds().bdi2000_poweron_cmds(["reset run"]) == []

    def test_list_with_name_flag(self):
        import tbot

        tbot.flags = {"poweron_cmds:nowdt"}
        with pytest.raises(RuntimeError, match="is a list"):
            load_poweron_cmds().bdi2000_poweron_cmds(["reset run"])

    def test_dict_without_flag_takes_default(self):
        assert load_poweron_cmds().bdi2000_poweron_cmds(CMDS) == ["reset run"]

    def test_dict_without_flag_and_default(self):
        cmds = {"nowdt": CMDS["nowdt"]}
        assert load_poweron_cmds().bdi2000_poweron_cmds(cmds) == []

    def test_dict_with_name_flag(self):
        import tbot

        tbot.flags = {"boardname:amc", "poweron_cmds:nowdt"}
        assert load_poweron_cmds().bdi2000_poweron_cmds(CMDS) == [
            "reset",
            "go 0x40000100",
        ]

    def test_dict_with_none_flag(self):
        import tbot

        tbot.flags = {"poweron_cmds:None"}
        assert load_poweron_cmds().bdi2000_poweron_cmds(CMDS) == []

    def test_dict_with_unknown_name(self):
        import tbot

        tbot.flags = {"poweron_cmds:foo"}
        with pytest.raises(RuntimeError, match=r"known are \['default', 'nowdt'\]"):
            load_poweron_cmds().bdi2000_poweron_cmds(CMDS)

    def test_two_flags(self):
        import tbot

        tbot.flags = {"poweron_cmds:default", "poweron_cmds:nowdt"}
        with pytest.raises(RuntimeError, match="more than one"):
            load_poweron_cmds().bdi2000_poweron_cmds(CMDS)

    def test_result_is_a_copy(self):
        cmds = load_poweron_cmds().bdi2000_poweron_cmds(CMDS)
        cmds.append("go")
        assert CMDS["default"] == ["reset run"]
