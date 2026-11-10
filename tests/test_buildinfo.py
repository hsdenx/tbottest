"""
Unit tests for tbottest/tc/buildinfo.py, with a /etc/buildinfo as
image-buildinfo writes it.
"""

import os

from conftest import load_module

buildinfo = load_module(
    "tbottest_tc_buildinfo",
    os.path.join(os.path.dirname(__file__), "..", "tbottest", "tc", "buildinfo.py"),
)

TEXT = """-----------------------
Build Configuration:  |
-----------------------
DISTRO = dummydistro
DISTRO_VERSION = 2.0.0
COMMON_FEATURES =
MY_BUILD_ID = ci-1388
DISTRO = dummydistro2
-----------------------
Layer Revisions:      |
-----------------------
meta-arm          = HEAD:caa36c53f796beb25d9b9f58b1b7a492e9987e15
meta-distro = feature/x:0a0d98c8132c53dfcac82a46e0225c3ff0d3dcec
meta-bsp = feature/x:7b8a7ef991ab8d3d226c935f12688279a635dc0d -- modified
meta              = patched-5d1aa5c8:a32cb715304bf463579d5a47c81f03f7fcc90f08
"""


class FakeLinux:
    def __init__(self, ret, text):
        self.result = (ret, text)
        self.commands = []

    def exec(self, *args):
        self.commands.append(args)
        return self.result


class TestParse:
    def test_variables_last_line_wins(self):
        variables, _ = buildinfo.buildinfo_parse(TEXT)
        assert variables["MY_BUILD_ID"] == "ci-1388"
        assert variables["DISTRO"] == "dummydistro2"
        assert variables["COMMON_FEATURES"] == ""

    def test_layers(self):
        _, layers = buildinfo.buildinfo_parse(TEXT)
        assert layers["meta-distro"] == {
            "branch": "feature/x",
            "revision": "0a0d98c8132c53dfcac82a46e0225c3ff0d3dcec",
            "modified": False,
        }
        assert layers["meta-arm"]["branch"] == "HEAD"
        assert layers["meta-bsp"]["modified"] is True
        assert layers["meta-bsp"]["revision"] == "7b8a7ef991ab8d3d226c935f12688279a635dc0d"
        assert layers["meta"]["branch"] == "patched-5d1aa5c8"

    def test_layer_names_are_no_variables(self):
        variables, _ = buildinfo.buildinfo_parse(TEXT)
        assert "meta-arm" not in variables


class TestCompare:
    def parsed(self):
        return buildinfo.buildinfo_parse(TEXT)

    def test_all_match(self):
        failed = buildinfo.buildinfo_compare(
            *self.parsed(), {"MY_BUILD_ID": "ci-1388"}, {"meta-distro": "0a0d98c"}
        )
        assert failed == []

    def test_other_build_id(self):
        failed = buildinfo.buildinfo_compare(*self.parsed(), {"MY_BUILD_ID": "ci-1390"}, {})
        assert failed == ["MY_BUILD_ID = ci-1388, expected ci-1390"]

    def test_missing_variable(self):
        failed = buildinfo.buildinfo_compare(*self.parsed(), {"OTHER_ID": "1"}, {})
        assert failed == ["OTHER_ID is not in the buildinfo"]

    def test_other_layer_revision(self):
        failed = buildinfo.buildinfo_compare(*self.parsed(), {}, {"meta-distro": "40c9334"})
        assert failed == ["layer meta-distro at 0a0d98c8132c53dfcac82a46e0225c3ff0d3dcec, expected 40c9334"]

    def test_missing_layer(self):
        failed = buildinfo.buildinfo_compare(*self.parsed(), {}, {"meta-gone": "1234"})
        assert failed == ["layer meta-gone is not in the buildinfo"]

    def test_modified_layer(self):
        failed = buildinfo.buildinfo_compare(*self.parsed(), {}, {"meta-bsp": "7b8a7ef"})
        assert failed == ["layer meta-bsp was built from a modified checkout"]

    def test_empty_expected_revision_does_not_match(self):
        failed = buildinfo.buildinfo_compare(*self.parsed(), {}, {"meta-distro": ""})
        assert len(failed) == 1


class TestCheck:
    def test_ok(self):
        lnx = FakeLinux(0, TEXT)
        assert buildinfo.lnx_check_buildinfo(lnx, {"MY_BUILD_ID": "ci-1388"}, {"meta-distro": "0a0d98c"})
        assert lnx.commands == [("cat", "/etc/buildinfo")]

    def test_mismatch(self):
        lnx = FakeLinux(0, TEXT)
        assert not buildinfo.lnx_check_buildinfo(lnx, {"MY_BUILD_ID": "ci-1"})

    def test_no_file(self):
        lnx = FakeLinux(1, "cat: can't open '/etc/buildinfo'")
        assert not buildinfo.lnx_check_buildinfo(lnx, {"MY_BUILD_ID": "ci-1388"})
