"""
Unit tests for newtbot_completion.py and the variable branch of
completions.sh.

The completion functions run against a package laid out as in a setup
made by create_setup.sh: ./cpltest/cpltest/... below the working
directory, with the repository directory ./cpltest in sys.path, as
newtbot_starter.py puts tbottest there.
"""

import ast
import os
import subprocess
import sys
import types

import pytest

from conftest import load_module

HERE = os.path.dirname(__file__)
REPO = os.path.join(HERE, "..")
completion = load_module("newtbot_completion", os.path.join(REPO, "newtbot_completion.py"))

BASH_COMPLETION = "/usr/share/bash-completion/bash_completion"


@pytest.fixture
def setup_dir(tmp_path, monkeypatch):
    repo = tmp_path / "cpltest"
    pkg = repo / "cpltest"
    (pkg / "tc").mkdir(parents=True)
    (repo / "tests").mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "tc" / "__init__.py").write_text("")
    (pkg / "tc" / "generic.py").write_text("def generic_all():\n    pass\n")
    (pkg / "tc" / "other.py").write_text("")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "interactive.py").write_text("def lab():\n    pass\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(repo))
    monkeypatch.syspath_prepend(str(tmp_path))
    for mod in list(sys.modules):
        if mod.split(".")[0] in ("cpltest", "config"):
            monkeypatch.delitem(sys.modules, mod)
    return tmp_path


class TestCompleteModule:
    def test_top_level_from_the_working_directory(self, setup_dir):
        assert list(completion.complete_module("cpl")) == ["cpltest"]

    def test_package_through_sys_path(self, setup_dir):
        # the package, not the tests directory of the repository
        assert list(completion.complete_module("cpltest.t")) == ["cpltest.tc"]

    def test_inside_a_package(self, setup_dir):
        expected = ["cpltest.tc.generic", "cpltest.tc.other"]
        assert list(completion.complete_module("cpltest.tc.")) == expected
        assert list(completion.complete_module("cpltest.tc")) == expected

    def test_in_the_working_directory(self, setup_dir):
        assert list(completion.complete_module("config.in")) == ["config.interactive"]

    def test_unknown(self, setup_dir):
        assert list(completion.complete_module("nosuch.x")) == []

    def test_parameters(self, setup_dir):
        assert list(completion.complete_module("cpltest.tc:x=1")) == []


class TestCompleteTestcase:
    def test_testcase_of_a_package_module(self, setup_dir):
        result = list(completion.complete_testcase("cpltest.tc.generic.gen"))
        assert result == ["cpltest.tc.generic.generic_all"]

    def test_module_name_first(self, setup_dir):
        assert list(completion.complete_testcase("cpltest.tc.gen")) == ["cpltest.tc.generic"]

    def test_testcase_in_the_working_directory(self, setup_dir):
        result = list(completion.complete_testcase("config.interactive.la"))
        assert result == ["config.interactive.lab"]

    def test_top_level(self, setup_dir):
        assert list(completion.complete_testcase("cpl")) == ["cpltest"]

    def test_unknown_module(self, setup_dir):
        assert list(completion.complete_testcase("nosuch.x")) == []

    def test_parameters(self, setup_dir):
        assert list(completion.complete_testcase("cpltest.tc.generic.x:a=1")) == []


def test_install():
    newbot = types.SimpleNamespace(complete_module=None, complete_testcase=None)
    completion.install(newbot)
    assert newbot.complete_module is completion.complete_module
    assert newbot.complete_testcase is completion.complete_testcase


def test_does_not_import_tbottest():
    """tbottest/__init__.py must not be imported before tbot set the flags"""
    tree = ast.parse(open(os.path.join(REPO, "newtbot_completion.py")).read())
    names = [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
    names += [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    assert not [n for n in names if n.split(".")[0] in ("tbottest", "tbot")]


@pytest.mark.skipif(not os.path.exists(BASH_COMPLETION), reason="no bash-completion")
@pytest.mark.parametrize(
    "word,expected",
    [("$cpltc", "$cpltcvar"), ("$", None)],
)
def test_completions_sh_variable_name(word, expected):
    script = f"""
source {BASH_COMPLETION}
source {os.path.join(REPO, "completions.sh")}
# _init_completion would complete the name too, but with a space after it
_init_completion() {{ echo INIT_COMPLETION; return 1; }}
cpltcvar=cpltest.tc
COMP_WORDS=(newtbot_starter.py '{word}')
COMP_CWORD=1
COMP_LINE="newtbot_starter.py {word}"
COMP_POINT=${{#COMP_LINE}}
_newbot newtbot_starter.py '{word}' newtbot_starter.py 2>/dev/null
printf '%s\\n' "${{COMPREPLY[@]}}"
"""
    out = subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, check=True
    ).stdout.split()
    assert "INIT_COMPLETION" not in out
    if expected is None:
        # every variable, each with the $ in front
        assert "$cpltcvar" in out and all(w.startswith("$") for w in out)
    else:
        assert out == [expected]
