"""
Unit tests for tbottest/initconfighelper.py.

get_tbot_arguments()/get_tbot_flags() are exercised through the
tbot.newbot.build_parser stub installed by conftest's
install_tbot_stubs() (a minimal -f/testcase-only parser -- see there
for what it does and doesn't cover). The inifile_get_* functions are
exercised end-to-end against real temp files via install_fake_initconfig's
copy_file, since that function does real file I/O with no tbot
dependency of its own.
"""

import os
import sys

import pytest

from conftest import install_fake_initconfig, load_module

install_fake_initconfig()

initconfighelper = load_module(
    "tbottest_initconfighelper",
    os.path.join(os.path.dirname(__file__), "..", "tbottest", "initconfighelper.py"),
)


@pytest.fixture(autouse=True)
def _reset_module_caches(monkeypatch):
    """
    initconfighelper caches its resolved values in module-level state
    (UUID_FILENAME, TBOTCONFIGPATH, _INIFILE_CACHE) so repeated calls
    within one tbot run are cheap. Reset all of it around every test
    so tests don't leak into each other.
    """
    monkeypatch.setattr(initconfighelper, "UUID_FILENAME", None)
    monkeypatch.setattr(initconfighelper, "TBOTCONFIGPATH", None)
    monkeypatch.setattr(initconfighelper, "_INIFILE_CACHE", {})
    old_argv = sys.argv
    yield
    sys.argv = old_argv


class TestGetLabSectionname:
    def test_no_labname_flag_returns_default(self):
        sys.modules["tbot"].flags = set()
        assert initconfighelper.get_lab_sectionname() == "LABHOST"

    def test_labname_flag_builds_section_name(self):
        sys.modules["tbot"].flags = {"labname:graefelfing"}
        assert initconfighelper.get_lab_sectionname() == "LABHOST_graefelfing"


class TestGetUniqueFilenameExtension:
    def test_stable_across_repeated_calls(self):
        first = initconfighelper.get_unique_filename_extension()
        second = initconfighelper.get_unique_filename_extension()
        assert first == second


class TestGetTbotArguments:
    def test_parses_flags_from_argv(self):
        sys.argv = ["tbot", "-f", "boardname:scale-mc"]
        args = initconfighelper.get_tbot_arguments()
        assert args.flags == ["boardname:scale-mc"]

    def test_parser_error_raises_runtimeerror_not_unboundlocalerror(self, monkeypatch):
        """
        Regression test: parser.parse_args() failing used to leave
        `args` unassigned, so the code after the try/except crashed
        with a confusing UnboundLocalError instead of surfacing the
        actual parse error. Note argparse's *normal* error path
        (unrecognized args, etc.) raises SystemExit, which the
        try/except never caught either way -- this exercises the
        other kind of failure that except Exception is actually meant
        to catch (e.g. a custom action raising during parsing).
        """

        class _BadParser:
            def add_argument(self, *a, **kw):
                pass

            def parse_args(self, *a, **kw):
                raise ValueError("boom")

        monkeypatch.setattr(initconfighelper, "build_parser", lambda: _BadParser())
        sys.argv = ["tbot"]
        with pytest.raises(RuntimeError, match="error parsing arguments"):
            initconfighelper.get_tbot_arguments()


class TestGetTbotFlags:
    def test_usetbotflags_reads_from_tbot_flags(self):
        sys.argv = ["tbot", "--usetbotflags"]
        sys.modules["tbot"].flags = ["boardname:scale-mc"]
        assert initconfighelper.get_tbot_flags() == ["boardname:scale-mc"]

    def test_without_usetbotflags_parses_argv(self):
        sys.argv = ["tbot", "-f", "boardname:scale-mc"]
        assert initconfighelper.get_tbot_flags() == ["boardname:scale-mc"]


class TestGetTbotconfigPath:
    def test_uses_tbotconfigpath_env_var(self, monkeypatch):
        monkeypatch.setenv("TBOTCONFIGPATH", "/some/config/path")
        assert initconfighelper.get_tbotconfig_path() == "/some/config/path"

    def test_falls_back_to_pythonpath_tbotconfig_entry(self, monkeypatch):
        monkeypatch.delenv("TBOTCONFIGPATH", raising=False)
        monkeypatch.setenv("PYTHONPATH", "/other:/some/path/tbotconfig:/more")
        assert initconfighelper.get_tbotconfig_path() == "/some/path/"

    def test_falls_back_to_cwd(self, monkeypatch):
        monkeypatch.delenv("TBOTCONFIGPATH", raising=False)
        monkeypatch.delenv("PYTHONPATH", raising=False)
        assert initconfighelper.get_tbotconfig_path() == os.getcwd()


class TestInifileGetTbotfilename:
    def test_default_path_when_no_flag_given(self, monkeypatch, tmp_path):
        monkeypatch.setenv("TBOTCONFIGPATH", str(tmp_path))
        sys.argv = ["tbot", "--usetbotflags"]
        sys.modules["tbot"].flags = []
        with pytest.raises(FileNotFoundError):
            # no such file exists -- just confirms it tried the
            # documented default location, not that the copy succeeds
            initconfighelper.inifile_get_tbotfilename()

    def test_relative_pathinifile_flag_is_resolved_against_cfgpath(
        self, monkeypatch, tmp_path
    ):
        src = tmp_path / "sub" / "rel.ini"
        src.parent.mkdir()
        src.write_text("hello=world\n")

        monkeypatch.setenv("TBOTCONFIGPATH", str(tmp_path))
        sys.argv = ["tbot", "--usetbotflags"]
        sys.modules["tbot"].flags = ["inifile:sub/rel.ini"]

        result = initconfighelper.inifile_get_tbotfilename()
        assert result.startswith(str(tmp_path) + "/sub/rel.ini-")
        assert os.path.exists(result)

    def test_absolute_pathinifile_flag_is_used_as_is(self, monkeypatch, tmp_path):
        """
        Regression test: the absolute-path check used to compare a
        single character against the two-character string "\\/" (a
        stray raw-string typo), which can never be equal -- so
        absolute paths were always (incorrectly) prefixed with
        cfgpath too, producing a nonexistent doubled path.
        """
        src = tmp_path / "abs.ini"
        src.write_text("hello=world\n")

        monkeypatch.setenv("TBOTCONFIGPATH", str(tmp_path))
        sys.argv = ["tbot", "--usetbotflags"]
        sys.modules["tbot"].flags = [f"inifile:{src}"]

        result = initconfighelper.inifile_get_tbotfilename()
        assert result.startswith(str(src) + "-")
        assert os.path.exists(result)

    def test_tmpfilepath_flag_overrides_destination_directory(
        self, monkeypatch, tmp_path
    ):
        src = tmp_path / "abs.ini"
        src.write_text("hello=world\n")
        destdir = tmp_path / "dest"
        destdir.mkdir()

        monkeypatch.setenv("TBOTCONFIGPATH", str(tmp_path))
        sys.argv = ["tbot", "--usetbotflags"]
        sys.modules["tbot"].flags = [f"inifile:{src}", f"tmpfilepath:{destdir}"]

        result = initconfighelper.inifile_get_tbotfilename()
        assert result.startswith(str(destdir) + "/abs.ini-")
        assert os.path.exists(result)

    def test_result_is_cached(self, monkeypatch, tmp_path):
        src = tmp_path / "abs.ini"
        src.write_text("hello=world\n")

        monkeypatch.setenv("TBOTCONFIGPATH", str(tmp_path))
        sys.argv = ["tbot", "--usetbotflags"]
        sys.modules["tbot"].flags = [f"inifile:{src}"]

        first = initconfighelper.inifile_get_tbotfilename()
        # change flags -- cached result must not change on a second call
        sys.modules["tbot"].flags = ["inifile:should-be-ignored.ini"]
        second = initconfighelper.inifile_get_tbotfilename()
        assert first == second

    def test_missing_separator_raises_runtimeerror(self, monkeypatch, tmp_path):
        monkeypatch.setenv("TBOTCONFIGPATH", str(tmp_path))
        sys.argv = ["tbot", "--usetbotflags"]
        sys.modules["tbot"].flags = ["inifile"]
        with pytest.raises(RuntimeError, match="seperator inifile flag"):
            initconfighelper.inifile_get_tbotfilename()


class TestInifileGetTbotboardfilename:
    def test_independent_cache_from_tbotfilename(self, monkeypatch, tmp_path):
        ini_src = tmp_path / "tbot.ini"
        ini_src.write_text("a=1\n")
        board_src = tmp_path / "board.ini"
        board_src.write_text("b=2\n")

        monkeypatch.setenv("TBOTCONFIGPATH", str(tmp_path))
        sys.argv = ["tbot", "--usetbotflags"]

        sys.modules["tbot"].flags = [f"inifile:{ini_src}"]
        inifile_result = initconfighelper.inifile_get_tbotfilename()

        sys.modules["tbot"].flags = [f"boardfile:{board_src}"]
        boardfile_result = initconfighelper.inifile_get_tbotboardfilename()

        assert inifile_result.startswith(str(ini_src) + "-")
        assert boardfile_result.startswith(str(board_src) + "-")
        assert inifile_result != boardfile_result

    def test_missing_separator_raises_runtimeerror(self, monkeypatch, tmp_path):
        monkeypatch.setenv("TBOTCONFIGPATH", str(tmp_path))
        sys.argv = ["tbot", "--usetbotflags"]
        sys.modules["tbot"].flags = ["boardfile"]
        with pytest.raises(RuntimeError, match="seperator boardfile flag"):
            initconfighelper.inifile_get_tbotboardfilename()
