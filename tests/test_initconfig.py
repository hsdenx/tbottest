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


def load_get_boardname(board_set_boardname=None, tbotjson=None):
    """generic_get_boardname(); with tbotjson (path) as for a JSON
    configuration, with the real reader of initconfig.py"""
    import types

    from conftest import load_initconfig_functions

    mod = load_definition(
        "tbottest_initconfig_generic_get_boardname_only",
        INITCONFIG_PATH,
        "generic_get_boardname",
        extra_src="import tbot\nBOARDNAME = None\nboard_set_boardname = None",
    )
    mod.board_set_boardname = board_set_boardname
    funcs = load_initconfig_functions()
    mod.init_read_jsonfile = funcs.init_read_jsonfile
    mod.init_section_get_config = funcs.init_section_get_config
    mod.inithelper = types.SimpleNamespace(
        config_is_json=lambda: tbotjson is not None,
        inifile_get_tbotfilename=lambda: tbotjson,
        get_lab_sectionname=lambda: "LABHOST",
    )
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

    def test_json_board_of_the_lab_section(self, tmp_path):
        import tbot

        tbot.flags = set()
        path = tmp_path / "tbot.json"
        path.write_text('{"LABHOST": {"board": "${flag:boardname:-BOARDNAME}"}}')
        assert load_get_boardname(tbotjson=str(path)).generic_get_boardname() == "BOARDNAME"

    def test_json_flag_wins(self, tmp_path):
        import tbot

        tbot.flags = {"boardname:other"}
        path = tmp_path / "tbot.json"
        path.write_text('{"LABHOST": {"board": "BOARDNAME"}}')
        assert load_get_boardname(tbotjson=str(path)).generic_get_boardname() == "other"

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


def _load_init_keys():
    from conftest import load_initconfig_functions

    return load_initconfig_functions(boardname="amc")


init_keys = _load_init_keys()


class TestInitGetConfigKeys:
    def _cp(self, sections):
        import configparser

        cp = configparser.RawConfigParser()
        cp.read_dict(sections)
        return cp

    def test_board_section_first_each_key_once(self):
        cp = self._cp(
            {
                "TC_amc": {"ub_env_b": "1", "linux_user": "x"},
                "TC": {"ub_env_a": "2", "ub_env_b": "3", "uboot_prompt": "=> "},
                "TC_other": {"ub_env_c": "4"},
            }
        )
        assert init_keys.init_get_config_keys(cp, "ub_env_") == ["ub_env_b", "ub_env_a"]

    def test_no_sections(self):
        assert init_keys.init_get_config_keys(self._cp({"default": {"a": "1"}}), "ub_env_") == []


class TestSectionConfig:
    """init_section_get_config() and the helpers built on it, as
    tests/conftest.py loads them from tbottest/initconfig.py"""

    @pytest.fixture
    def ini(self):
        from conftest import load_initconfig_functions

        return load_initconfig_functions(boardname="amc", labsection="LABHOST_lab2")

    @pytest.fixture
    def cp(self):
        import configparser

        cp = configparser.RawConfigParser()
        cp.read_dict(
            {
                "LABHOST": {"hostname": "cm4-lab-2"},
                "LABHOST_lab2": {"hostname": "cm4-lab", "uselocking": "no"},
                "BUILDHOST": {"name": "b", "docker": "None", "install": "Yes"},
                "BUILDHOST_local": {"name": "l"},
                "TC": {"ignore_hostkey": "false", "tmpdir": "None"},
                "TC_amc": {"ignore_hostkey": "on"},
            }
        )
        return cp

    def test_value_as_written(self, ini, cp):
        assert ini.init_section_get_config(cp, "BUILDHOST", "docker") == "None"

    def test_default_for_missing_key_and_section(self, ini, cp):
        assert ini.init_section_get_config(cp, "BUILDHOST", "port", 22) == 22
        assert ini.init_section_get_config(cp, "SSHMACHINE", "name", None) is None

    def test_required_key_missing(self, ini, cp):
        with pytest.raises(RuntimeError, match=r"key port missing in section \[BUILDHOST\]"):
            ini.init_section_get_config(cp, "BUILDHOST", "port")
        with pytest.raises(RuntimeError, match=r"section \[SSHMACHINE\]"):
            ini.init_section_get_config(cp, "SSHMACHINE", "name")

    def test_lab_section_from_inithelper(self, ini, cp):
        assert ini.init_lab_get_config(cp, "hostname") == "cm4-lab"
        assert ini.init_lab_get_config(cp, "testdir", None) is None
        with pytest.raises(RuntimeError, match=r"LABHOST_lab2"):
            ini.init_lab_get_config(cp, "tftproot")

    @pytest.mark.parametrize(
        "value,result", [("1", True), ("Yes", True), ("ON", True), ("0", False), ("off", False)]
    )
    def test_config_to_bool(self, ini, value, result):
        assert ini.init_config_to_bool(value) is result

    def test_config_to_bool_invalid(self, ini):
        with pytest.raises(ValueError, match="not a boolean: maybe"):
            ini.init_config_to_bool("maybe")

    def test_section_bool(self, ini, cp):
        assert ini.init_section_get_config_bool(cp, "BUILDHOST", "install", False) is True
        assert ini.init_section_get_config_bool(cp, "BUILDHOST", "missing", True) is True

    def test_tc_bool_board_section_first(self, ini, cp):
        assert ini.init_get_config_bool(cp, "ignore_hostkey", False) is True
        cp.remove_option("TC_amc", "ignore_hostkey")
        assert ini.init_get_config_bool(cp, "ignore_hostkey", True) is False

    def test_tc_bool_none_is_default(self, ini, cp):
        assert ini.init_get_config_bool(cp, "tmpdir", True) is True
        assert ini.init_get_config_bool(cp, "missing", False) is False

    def test_sections(self, ini, cp):
        assert ini.init_has_section(cp, "BUILDHOST_local")
        assert not ini.init_has_section(cp, "SSHMACHINE")
        assert ini.init_find_sections(cp, "BUILDHOST") == ["BUILDHOST", "BUILDHOST_local"]
        assert ini.init_find_sections(cp, "SSHMACHINE") == []

    def test_methods_of_initbotconfig(self, cp):
        from conftest import FakeIniTBotConfig

        cfgt = FakeIniTBotConfig(cp, labsection="LABHOST_lab2")
        assert cfgt.get_lab_config("uselocking") == "no"
        assert cfgt.get_section_config("BUILDHOST_local", "name") == "l"
        assert cfgt.get_section_config_bool("BUILDHOST", "install", False) is True
        assert cfgt.has_section("TC_amc")
        assert cfgt.find_sections("LABHOST") == ["LABHOST", "LABHOST_lab2"]


class TestTestcaseSection:
    """
    sections of the board configuration while a testcase runs, see
    init_testcase() and init_config_sections()
    """

    def _cp(self, sections):
        import configparser

        cp = configparser.RawConfigParser()
        cp.read_dict(sections)
        return cp

    def test_sections_without_testcase(self):
        assert init_keys.init_current_testcase() is None
        assert init_keys.init_config_sections() == ["TC_amc", "TC"]

    def test_sections_with_testcase(self):
        with init_keys.init_testcase("tc1"):
            assert init_keys.init_current_testcase() == "tc1"
            assert init_keys.init_config_sections() == ["TC_amc.tc1", "TC_amc", "TC"]
        assert init_keys.init_config_sections() == ["TC_amc", "TC"]

    def test_nested_testcases_restore_the_outer_one(self):
        with init_keys.init_testcase("outer"):
            with init_keys.init_testcase("inner"):
                assert init_keys.init_current_testcase() == "inner"
            assert init_keys.init_current_testcase() == "outer"
        assert init_keys.init_current_testcase() is None

    def test_testcase_reset_after_exception(self):
        try:
            with init_keys.init_testcase("tc1"):
                raise ValueError("boom")
        except ValueError:
            pass
        assert init_keys.init_current_testcase() is None

    def test_lookup_order(self):
        cp = self._cp(
            {
                "TC_amc.tc1": {"a": "testcase"},
                "TC_amc": {"a": "board", "b": "board"},
                "TC": {"a": "all", "b": "all", "c": "all"},
            }
        )
        get = init_keys.init_get_config
        with init_keys.init_testcase("tc1"):
            assert get(cp, "a", "x") == "testcase"
            assert get(cp, "b", "x") == "board"
            assert get(cp, "c", "x") == "all"
            assert get(cp, "d", "x") == "x"
        with init_keys.init_testcase("tc2"):
            assert get(cp, "a", "x") == "board"
        assert get(cp, "a", "x") == "board"

    def test_no_section_for_a_testcase_on_all_boards(self):
        cp = self._cp({"TC_tc1": {"a": "testcase"}, "TC": {"a": "all"}})
        with init_keys.init_testcase("tc1"):
            assert init_keys.init_get_config(cp, "a", "x") == "all"

    def test_none_in_testcase_section_hides_the_others(self):
        cp = self._cp({"TC_amc.tc1": {"a": "None"}, "TC_amc": {"a": "board"}})
        with init_keys.init_testcase("tc1"):
            assert init_keys.init_get_config(cp, "a", "x") is None

    def test_int_and_literal(self):
        cp = self._cp(
            {
                "TC_amc.tc1": {"count": "3", "dmesg": "['Linux version']"},
                "TC": {"count": "1", "dmesg": "[]"},
            }
        )
        with init_keys.init_testcase("tc1"):
            assert init_keys.init_get_config_int(cp, "count", "0") == 3
            assert init_keys.init_get_config_literal(cp, "dmesg", "[]") == ["Linux version"]
        assert init_keys.init_get_config_int(cp, "count", "0") == 1
        assert init_keys.init_get_config_literal(cp, "dmesg", "[]") == []
        assert init_keys.init_get_config_literal(cp, "leds", "None") is None

    def test_keys_testcase_section_first(self):
        cp = self._cp(
            {
                "TC_amc.tc1": {"ub_env_c": "1"},
                "TC_amc": {"ub_env_b": "1"},
                "TC": {"ub_env_a": "2", "ub_env_c": "3"},
            }
        )
        with init_keys.init_testcase("tc1"):
            assert init_keys.init_get_config_keys(cp, "ub_env_") == [
                "ub_env_c",
                "ub_env_b",
                "ub_env_a",
            ]
