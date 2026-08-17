"""
Unit tests for tbottest/builders.py's genericbuilder/genericbuilderlocal.

Uses the conftest tbot/tbot.machine stubs (connector.SSHConnector,
linux.Bash, linux.Builder etc. resolve to interchangeable placeholder
classes there -- real MRO safety of putting _BuilderPathsMixin first
was verified separately against the actual tbot package, not
re-checked here) plus a real configparser.ConfigParser backing
tbottest.initconfig.IniTBotConfig via install_fake_initbotconfig().
"""

import os
import sys

from conftest import install_fake_initbotconfig, load_module


def load_builders(sections):
    install_fake_initbotconfig(sections)
    return load_module(
        "tbottest_builders",
        os.path.join(os.path.dirname(__file__), "..", "tbottest", "builders.py"),
    )


BASE_SECTIONS = {
    "BUILDHOST": {
        "name": "buildhost",
        "username": "user",
        "hostname": "build.example.com",
        "dl_dir": "downloads",
        "sstate_dir": "sstate",
        "workdir": "relwork",
        "kas_ref_dir": "/kas/ref",
        "initcmd": '["echo hello-remote"]',
    },
    "BUILDHOST_local": {
        "name": "localbuild",
        "dl_dir": "dl",
        "sstate_dir": "sstate",
        "workdir": "/abs/localwork",
        "kas_ref_dir": "/kas/ref-local",
        "initcmd": '["echo hello-local"]',
    },
}


class FakeExecHost:
    def __init__(self):
        self.commands = []

    def exec0(self, *args):
        self.commands.append(tuple(str(a) for a in args))
        return ""


class TestGenericbuilderConfig:
    def test_reads_buildhost_section_by_default(self):
        builders = load_builders(BASE_SECTIONS)
        gb = builders.genericbuilder()
        assert gb.sn == "BUILDHOST"
        assert gb.name == "buildhost"
        assert gb.username == "user"
        assert gb.hostname == "build.example.com"

    def test_relative_workdir_is_prefixed_with_cwd(self):
        builders = load_builders(BASE_SECTIONS)
        gb = builders.genericbuilder()
        gb.exec0 = FakeExecHost().exec0
        assert str(gb.workdir).endswith(os.getcwd() + "/relwork")

    def test_absolute_kas_ref_dir_used_as_is(self):
        builders = load_builders(BASE_SECTIONS)
        gb = builders.genericbuilder()
        gb.exec0 = FakeExecHost().exec0
        assert str(gb.kas_ref_dir).endswith("/kas/ref")

    def test_port_defaults_to_22_when_not_configured(self):
        builders = load_builders(BASE_SECTIONS)
        gb = builders.genericbuilder()
        assert gb.port == 22

    def test_port_read_from_config(self):
        sections = dict(BASE_SECTIONS)
        sections["BUILDHOST"] = dict(sections["BUILDHOST"], port="2222")
        builders = load_builders(sections)
        gb = builders.genericbuilder()
        assert gb.port == 2222


class TestGenericbuilderlocalConfig:
    def test_reads_buildhost_local_section(self):
        builders = load_builders(BASE_SECTIONS)
        gbl = builders.genericbuilderlocal()
        assert gbl.sn == "BUILDHOST_local"
        assert gbl.name == "localbuild"

    def test_absolute_workdir_used_as_is(self):
        builders = load_builders(BASE_SECTIONS)
        gbl = builders.genericbuilderlocal()
        gbl.exec0 = FakeExecHost().exec0
        assert str(gbl.workdir).endswith("/abs/localwork")

    def test_missing_section_falls_back_to_placeholder(self):
        builders = load_builders({"BUILDHOST": BASE_SECTIONS["BUILDHOST"]})
        gbl = builders.genericbuilderlocal()
        assert gbl.name == "NOTDEFINED please add BUILDHOST_local in tbot.ini"
        assert gbl.dl_dir == "NOTDEFINED please add BUILDHOST_local in tbot.ini"
        assert gbl.sstate_dir == "NOTDEFINED please add BUILDHOST_local in tbot.ini"


class TestInitCommandsRunOncePerClass:
    def test_both_classes_run_their_own_initcmd_independently(self):
        """
        Regression test: genericbuilder.init() and
        genericbuilderlocal.init() used to share one hardcoded
        "BHINIT" cache key, so whichever class's init() ran first
        marked the *other* class as already-initialized too --
        genericbuilderlocal's initcmd silently never ran if
        genericbuilder.init() had already executed in the same
        process.
        """
        builders = load_builders(BASE_SECTIONS)
        gb = builders.genericbuilder()
        gb.exec0 = FakeExecHost().exec0
        gbl = builders.genericbuilderlocal()
        gbl.exec0 = FakeExecHost().exec0

        gb.init()
        gbl.init()

        assert any("hello-remote" in c for cmd in gb.exec0.__self__.commands for c in cmd)
        assert any("hello-local" in c for cmd in gbl.exec0.__self__.commands for c in cmd)

    def test_repeated_init_on_same_class_runs_initcmd_only_once(self):
        builders = load_builders(BASE_SECTIONS)
        gb1 = builders.genericbuilder()
        gb1.exec0 = FakeExecHost().exec0
        gb1.init()
        call_count_after_first = len(gb1.exec0.__self__.commands)

        gb2 = builders.genericbuilder()
        gb2.exec0 = FakeExecHost().exec0
        gb2.init()

        assert gb2.exec0.__self__.commands == []
        assert call_count_after_first > 0


class TestBuildernameFlag:
    def test_buildername_flag_selects_matching_section(self, monkeypatch):
        sections = dict(BASE_SECTIONS)
        sections["BUILDHOST_th2"] = dict(
            BASE_SECTIONS["BUILDHOST"], name="th2builder"
        )
        install_fake_initbotconfig(sections)

        tbot_mod = sys.modules["tbot"]
        monkeypatch.setattr(tbot_mod, "flags", {"buildername:th2"})

        builders = load_module(
            "tbottest_builders_th2",
            os.path.join(os.path.dirname(__file__), "..", "tbottest", "builders.py"),
        )
        gb = builders.genericbuilder()
        assert gb.sn == "BUILDHOST_th2"
        assert gb.name == "th2builder"
