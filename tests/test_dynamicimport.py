"""
Unit tests for tbottest/dynamicimport.py: the "old setup"
(boardspecific.py directly under tbotconfig/) vs. "new setup" (path
derived from the -f inifile:... tbot flag) path resolution, and a
regression test for the get_boardmodule_import() error-message bug
(it used to reference an undefined "importpath" name in its
except-branch, raising NameError instead of the intended
RuntimeError).

get_import_path()/get_boardmodulepath_import()/get_boardmodule_import()
memoize their result in module-level globals, so each test here loads
a fresh copy of the module rather than reusing one across tests.
"""

import os
import sys

import pytest

from conftest import load_module

DYNAMICIMPORT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "tbottest", "dynamicimport.py"
)

_counter = [0]


def fresh_dynamicimport():
    _counter[0] += 1
    return load_module(f"tbottest_dynamicimport_{_counter[0]}", DYNAMICIMPORT_PATH)


class TestGetImportPath:
    def test_new_setup_reads_inifile_flag(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mod = fresh_dynamicimport()
        sys.modules["tbot"].flags = {"inifile:tbotconfig/myboard/tbot.ini"}
        assert mod.get_import_path() == "tbotconfig.myboard"

    def test_old_setup_detected_via_boardspecific_py(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "tbotconfig").mkdir()
        (tmp_path / "tbotconfig" / "boardspecific.py").write_text("")
        mod = fresh_dynamicimport()
        # even with an inifile flag present, the old-setup file check
        # must win (it's checked first)
        sys.modules["tbot"].flags = {"inifile:tbotconfig/myboard/tbot.ini"}
        assert mod.get_import_path() == "tbotconfig"

    def test_result_is_memoized(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mod = fresh_dynamicimport()
        sys.modules["tbot"].flags = {"inifile:tbotconfig/first/tbot.ini"}
        first = mod.get_import_path()
        sys.modules["tbot"].flags = {"inifile:tbotconfig/second/tbot.ini"}
        second = mod.get_import_path()
        assert first == second == "tbotconfig.first"

    def test_nested_inifile_path(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mod = fresh_dynamicimport()
        sys.modules["tbot"].flags = {"inifile:tbotconfig/toptica/scale/tbot.ini"}
        assert mod.get_import_path() == "tbotconfig.toptica.scale"


class TestGetBoardmodulepathImport:
    def test_appends_boardspecific(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mod = fresh_dynamicimport()
        sys.modules["tbot"].flags = {"inifile:tbotconfig/myboard/tbot.ini"}
        assert mod.get_boardmodulepath_import() == "tbotconfig.myboard.boardspecific"


class TestGetBoardcallbackpathImport:
    def test_appends_labcallbacks(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mod = fresh_dynamicimport()
        sys.modules["tbot"].flags = {"inifile:tbotconfig/myboard/tbot.ini"}
        assert mod.get_boardcallbackpath_import() == "tbotconfig.myboard.labcallbacks"


class TestGetBoardmoduleImport:
    def test_import_failure_raises_runtimeerror_with_real_path(self, tmp_path, monkeypatch):
        """
        Regression test for the "importpath" NameError bug: importing
        a nonexistent module must surface as a clear RuntimeError
        naming the actual import path, not crash with an unrelated
        NameError that masks the original ImportError.
        """
        monkeypatch.chdir(tmp_path)
        mod = fresh_dynamicimport()
        sys.modules["tbot"].flags = {"inifile:tbotconfig/doesnotexist/tbot.ini"}

        with pytest.raises(RuntimeError, match="tbotconfig.doesnotexist.boardspecific"):
            mod.get_boardmodule_import()
