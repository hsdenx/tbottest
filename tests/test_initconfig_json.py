"""
Unit tests for the JSON configuration of tbottest/initconfig.py: the
expressions ${env:}, ${flag:}, ${lab:} and ${tbot:}, the conversion of
JSON values to the strings configparser holds, the JSON reader, and the
way back from a configparser to JSON. The functions come from
initconfig.py itself, see conftest.load_initconfig_functions().
"""

import ast
import configparser
import json

import pytest

from conftest import load_initconfig_functions


@pytest.fixture
def ini():
    return load_initconfig_functions(boardname="BOARDNAME", labsection="LABHOST")


@pytest.fixture
def tbotcfgp():
    cp = configparser.RawConfigParser(interpolation=configparser.ExtendedInterpolation())
    cp.read_dict(
        {
            "LABHOST": {"serverip": "192.168.3.1", "nfs_base_path": "/data/srv/NFS"},
            "IPSETUP_BOARDNAME_eth0": {"serverip": "${LABHOST:serverip}", "ipaddr": "192.168.3.45"},
        }
    )
    return cp


class TestSubstitute:
    def test_env(self, ini, monkeypatch):
        monkeypatch.setenv("TBOTTEST_X", "abc")
        assert ini.init_config_substitute("a-${env:TBOTTEST_X}-b", []) == "a-abc-b"

    def test_env_default(self, ini, monkeypatch):
        monkeypatch.delenv("TBOTTEST_X", raising=False)
        assert ini.init_config_substitute("${env:TBOTTEST_X:-/tmp}", []) == "/tmp"

    def test_missing_without_default(self, ini, monkeypatch):
        monkeypatch.delenv("TBOTTEST_X", raising=False)
        with pytest.raises(RuntimeError, match="env TBOTTEST_X is not set and has no default"):
            ini.init_config_substitute("${env:TBOTTEST_X}", [], where="tbot.json")

    def test_flag_value_and_plain_flag(self, ini):
        flags = ["kasvariant:glibc", "silent"]
        assert ini.init_config_substitute("${flag:kasvariant}", flags) == "glibc"
        assert ini.init_config_substitute("${flag:silent}", flags) == "True"

    def test_flag_name_must_match(self, ini):
        assert ini.init_config_substitute("${flag:kas:-x}", ["kasvariant:glibc"]) == "x"

    def test_default_only_used_when_missing(self, ini):
        # the default would raise, but the flag is set
        assert ini.init_config_substitute("${flag:a:-${flag:missing}}", ["a:1"]) == "1"

    def test_nested_default(self, ini):
        text = "${flag:rootfsname:-${flag:img:-core-image-minimal}}"
        assert ini.init_config_substitute(text, []) == "core-image-minimal"

    def test_configparser_reference_kept_with_expression_inside(self, ini):
        text = "${KASVARIANT_${flag:kasvariant:-musl}:kasfile}"
        assert ini.init_config_substitute(text, []) == "${KASVARIANT_musl:kasfile}"
        assert ini.init_config_substitute(text, ["kasvariant:glibc"]) == "${KASVARIANT_glibc:kasfile}"

    def test_escapes_and_plain_dollar(self, ini):
        text = "console=$${console} cost $5 ${board}"
        assert ini.init_config_substitute(text, []) == text

    def test_lab_and_tbot(self, ini, tbotcfgp):
        value = ini.init_config_substitute("${lab:nfs_base_path}/BOARDNAME", [], tbotcfgp)
        assert value == "/data/srv/NFS/BOARDNAME"
        text = "${tbot:IPSETUP_BOARDNAME_eth0:serverip}"
        assert ini.init_config_substitute(text, [], tbotcfgp) == "192.168.3.1"

    def test_lab_only_in_board_file(self, ini):
        with pytest.raises(RuntimeError, match="works in the board file only"):
            ini.init_config_substitute("${lab:nfs_base_path}", [], None, "tbot.json")

    def test_unbalanced(self, ini):
        with pytest.raises(RuntimeError, match="unbalanced"):
            ini.init_config_substitute("${flag:a", [])


class TestValueToStr:
    @pytest.mark.parametrize(
        "value,result",
        [("text", "text"), (True, "True"), (False, "False"), (None, "None"), (3, "3"),
         (["a", 1], "['a', 1]"), ({"k": "v"}, "{'k': 'v'}")],
    )
    def test_conversion(self, ini, value, result):
        assert ini.init_json_value_to_str(value) == result

    def test_expressions_inside_lists(self, ini):
        subst = lambda s: ini.init_config_substitute(s, ["silent"])  # noqa: E731
        value = [{"name": "console", "val": "${flag:silent}"}]
        assert ini.init_json_value_to_str(value, subst) == "[{'name': 'console', 'val': 'True'}]"


class TestReadJson:
    def _write(self, tmp_path, name, data):
        path = tmp_path / name
        path.write_text(json.dumps(data))
        return str(path)

    def test_board_file(self, ini, tbotcfgp, tmp_path):
        path = self._write(tmp_path, "BOARDNAME.json", {
            "default": {
                "machine": "MACHINE",
                "kasvariant": "${flag:kasvariant:-musl}",
                "kasymlname": "${KASVARIANT_${flag:kasvariant:-musl}:kasfile}",
                "nfs_path": "${lab:nfs_base_path}/${machine}/${kasvariant}",
                "serverip": "${tbot:IPSETUP_BOARDNAME_eth0:serverip}",
            },
            "KASVARIANT_musl": {"kasfile": "musl.yml"},
            "KASVARIANT_glibc": {"kasfile": "glibc.yml"},
            "TC": {"ub_env": [{"name": "args", "val": "console=$${console}"}], "flag": True},
        })
        cp = ini.init_read_jsonfile(path, ["kasvariant:glibc"], tbotcfgp)
        assert cp.get("default", "kasymlname") == "glibc.yml"
        assert cp.get("default", "nfs_path") == "/data/srv/NFS/MACHINE/glibc"
        assert cp.get("default", "serverip") == "192.168.3.1"
        assert cp.get("TC", "ub_env") == "[{'name': 'args', 'val': 'console=${console}'}]"
        assert ini.init_config_to_bool(cp.get("TC", "flag")) is True
        cp = ini.init_read_jsonfile(path, [], tbotcfgp)
        assert cp.get("default", "kasymlname") == "musl.yml"

    def test_needs_sections(self, ini, tmp_path):
        path = self._write(tmp_path, "bad.json", {"key": "value"})
        with pytest.raises(RuntimeError, match="needs an object of sections"):
            ini.init_read_jsonfile(path, [])

    def test_read_configfile_by_name(self, ini, tmp_path):
        jpath = self._write(tmp_path, "t.json", {"LABHOST": {"a": "1"}})
        ipath = tmp_path / "t.ini"
        ipath.write_text("[LABHOST]\na = 2\n")
        assert ini.init_read_configfile(jpath).get("LABHOST", "a") == "1"
        assert ini.init_read_configfile(str(ipath)).get("LABHOST", "a") == "2"


class TestToJson:
    INI = """[LABHOST]
board = BOARDNAME
tftpsubdir = ${board}/20261001
broken = ${nothere}
labinit = ["sudo true"]
"""

    def test_raw_and_resolved(self, ini, tmp_path):
        path = tmp_path / "t.ini"
        path.write_text(self.INI)
        cp = ini.init_read_inifile(str(path))
        raw = ini.init_config_to_json_dict(cp)
        assert raw["LABHOST"]["tftpsubdir"] == "${board}/20261001"
        assert raw["LABHOST"]["labinit"] == ["sudo true"]
        res = ini.init_config_to_json_dict(cp, resolved=True)
        assert res["LABHOST"]["tftpsubdir"] == "BOARDNAME/20261001"
        assert res["LABHOST"]["broken"] == "${nothere}"

    def test_round_trip(self, ini, tmp_path):
        path = tmp_path / "t.ini"
        path.write_text(self.INI.replace("broken = ${nothere}\n", ""))
        cp = ini.init_read_inifile(str(path))
        jpath = tmp_path / "t.json"
        jpath.write_text(json.dumps(ini.init_config_to_json_dict(cp)))
        back = ini.init_read_jsonfile(str(jpath), [])

        def value(v):
            # lists come back as Python literal, read as tbottest reads them
            try:
                return ast.literal_eval(v)
            except Exception:
                return v

        for key in cp.options("LABHOST"):
            assert value(back.get("LABHOST", key)) == value(cp.get("LABHOST", key))


class TestIniExpressions:
    def test_board_ini_reads_the_lab_section(self, ini, tbotcfgp, tmp_path):
        path = tmp_path / "BOARDNAME.ini"
        path.write_text(
            "[TC]\n"
            "ub_env = [{'name': 'tftpp', 'val': '${lab:nfs_base_path}'}, "
            "{'name': 'x', 'val': '$${console}'}]\n"
            "kasvariant = ${flag:kasvariant:-musl}\n"
        )
        cp = ini.init_substitute_configparser(
            ini.init_read_inifile(str(path)), ["kasvariant:glibc"], tbotcfgp, str(path)
        )
        assert cp.get("TC", "ub_env") == (
            "[{'name': 'tftpp', 'val': '/data/srv/NFS'}, {'name': 'x', 'val': '${console}'}]"
        )
        assert cp.get("TC", "kasvariant") == "glibc"
