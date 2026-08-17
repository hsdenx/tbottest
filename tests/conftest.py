"""
Shared test infrastructure for pure-logic unit tests of tbottest.

Most tbottest modules have import-time side effects that require a
full tbot + board environment (tbotconfig/<board>/*.ini, tbot flags,
a real lab/board connection) -- see tbottest/initconfig.py, which
resolves and imports a board-specific module as soon as it is
imported. That makes it impossible to `import tbottest.xxx` directly
in a plain unit test.

To still unit-test the pure logic in these modules (string/config
parsing, retry loops, ...), this conftest installs lightweight
stand-ins for the tbot/tbot.machine modules into sys.modules, and
provides load_module() to import a single tbottest source file
directly from its path (bypassing tbottest/__init__.py and the
package import chain that would otherwise pull in a real board
environment).

These tests intentionally do NOT exercise anything that talks to
real hardware (lab hosts, boards, SSH/serial channels) -- that is
covered by tbot's own selftest suite and by running tbot testcases
against real hardware, not by this unit test suite.
"""

import argparse
import importlib.util
import sys
import types

import pytest


class _AnyAttrModule(types.ModuleType):
    """
    A module stand-in that returns a harmless placeholder for any
    attribute access. Used for tbot submodules that are only ever
    referenced in type hints (e.g. "board.UBootShell") by the code
    under test, never actually called.
    """

    def __getattr__(self, name):
        class _Placeholder:
            def __class_getitem__(cls, item):
                return cls

        return _Placeholder


class _ChainableNoop:
    """Stands in for tbot.log.c(...): supports arbitrary chained
    attribute access/color methods and is callable, always
    returning itself."""

    def __getattr__(self, name):
        return self

    def __call__(self, *args, **kwargs):
        return self


class _NoopCtxManager:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def install_tbot_stubs() -> None:
    """
    Install stand-ins for tbot/tbot.machine.* into sys.modules. Safe
    to call more than once (e.g. once per test module import).
    """
    tbot_mod = types.ModuleType("tbot")
    tbot_mod.flags = set()

    log_mod = types.ModuleType("tbot.log")
    log_mod.message = lambda *a, **kw: None
    log_mod.c = lambda *a, **kw: _ChainableNoop()
    tbot_mod.log = log_mod

    def testcase(f):
        return f

    tbot_mod.testcase = testcase
    tbot_mod.ctx = lambda: _NoopCtxManager()
    tbot_mod.role = types.SimpleNamespace(
        LocalHost=object(),
        LabHost=object(),
        BoardLinux=object(),
        BoardUBoot=object(),
        Board=object(),
    )
    tbot_mod.log_event = types.SimpleNamespace(
        command=lambda *a, **kw: _NoopCtxManager()
    )
    tbot_mod.selectable = types.SimpleNamespace(printed=False)

    def _build_parser():
        # minimal stand-in for tbot.newbot.build_parser(): only the
        # pieces initconfighelper.py actually reads (-f flags, testcase)
        p = argparse.ArgumentParser(prog="tbot", fromfile_prefix_chars="@")
        p.add_argument("-f", dest="flags", action="append", default=[])
        p.add_argument("testcase", nargs="*")
        return p

    newbot_mod = types.ModuleType("tbot.newbot")
    newbot_mod.build_parser = _build_parser
    tbot_mod.newbot = newbot_mod

    machine_mod = types.ModuleType("tbot.machine")
    linux_mod = _AnyAttrModule("tbot.machine.linux")

    class FakePath(str):
        def __truediv__(self, other):
            return FakePath(f"{self}/{other}")

        def _local_str(self):
            return str(self)

    class LinuxShell:
        pass

    class Raw(str):
        pass

    class Workdir:
        @staticmethod
        def static(host, path):
            return FakePath(str(path))

    linux_mod.LinuxShell = LinuxShell
    linux_mod.Path = FakePath
    linux_mod.path = types.SimpleNamespace(Path=FakePath)
    linux_mod.Raw = Raw
    linux_mod.Pipe = "|"
    linux_mod.Workdir = Workdir
    machine_mod.linux = linux_mod

    board_mod = _AnyAttrModule("tbot.machine.board")
    machine_mod.board = board_mod

    connector_mod = _AnyAttrModule("tbot.machine.connector")
    machine_mod.connector = connector_mod

    class Optional:
        def __class_getitem__(cls, item):
            return cls

    ctx_mod = types.ModuleType("tbot.context")
    ctx_mod.Optional = Optional

    tc_mod = types.ModuleType("tbot.tc")
    tc_shell_mod = types.ModuleType("tbot.tc.shell")
    tc_shell_mod.copy = lambda *a, **kw: None

    for name, mod in [
        ("tbot", tbot_mod),
        ("tbot.log", log_mod),
        ("tbot.newbot", newbot_mod),
        ("tbot.machine", machine_mod),
        ("tbot.machine.linux", linux_mod),
        ("tbot.machine.board", board_mod),
        ("tbot.machine.connector", connector_mod),
        ("tbot.context", ctx_mod),
        ("tbot.tc", tc_mod),
        ("tbot.tc.shell", tc_shell_mod),
    ]:
        sys.modules[name] = mod


def install_real_submodule(dotted_name: str, path: str) -> None:
    """
    Load a real tbottest submodule (one with no heavy import-time
    side effects of its own, e.g. tbottest/common/utils.py) and
    register it in sys.modules under its real dotted name, so other
    modules under test that do e.g.
    "from tbottest.common.utils import string_to_dict" resolve it via
    the normal import system instead of failing with
    "No module named 'tbottest.common'; 'tbottest' is not a package".
    """
    parts = dotted_name.split(".")
    pkg = ""
    for part in parts[:-1]:
        pkg = f"{pkg}.{part}" if pkg else part
        sys.modules.setdefault(pkg, types.ModuleType(pkg))
    sys.modules[dotted_name] = load_module(dotted_name, path)


def install_fake_initconfig(boardname: str = "testboard") -> None:
    """
    Install a minimal fake tbottest.initconfig module, for testing
    modules (tc/common.py, common/boardlocking.py, ...) that only
    need generic_get_boardname() from it, without pulling in the
    real module's board-environment-resolving import-time side
    effects.
    """
    ini_mod = types.ModuleType("tbottest.initconfig")
    ini_mod.generic_get_boardname = lambda: boardname

    def copy_file(filename, newfile):
        with open(filename, "rt") as fin:
            data = fin.read()
        with open(newfile, "wt") as fout:
            fout.write(data)

    ini_mod.copy_file = copy_file
    sys.modules.setdefault("tbottest", types.ModuleType("tbottest"))
    sys.modules["tbottest.initconfig"] = ini_mod


def load_module(name: str, path: str):
    """
    Import a single module directly from its file path, bypassing
    tbottest/__init__.py and any package-level import chain.
    """
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_definition(name: str, path: str, defname: str, extra_src: str = ""):
    """
    Extract a single top-level class/function definition (by source
    text, via ast) from `path` and exec it in a fresh module. Used
    for testing a self-contained piece (e.g. a metaclass) of a module
    whose *other* top-level code has import-time side effects that
    require a full board environment, without duplicating that piece
    into a separate, driftable copy: this always reflects whatever is
    currently in `path`.

    extra_src, if given, is executed before the extracted definition
    (e.g. to provide "import typing" if the definition needs it).
    """
    import ast

    src = open(path).read()
    tree = ast.parse(src)
    for node in tree.body:
        if getattr(node, "name", None) == defname:
            def_src = ast.get_source_segment(src, node)
            break
    else:
        raise AssertionError(f"{defname!r} not found as a top-level definition in {path}")

    mod = types.ModuleType(name)
    exec(compile(extra_src + "\n" + def_src, path, "exec"), mod.__dict__)
    return mod


install_tbot_stubs()


@pytest.fixture(autouse=True)
def _reset_tbot_flags():
    """
    tbot.flags (from the stub installed above) is shared, mutable,
    process-global state -- reset it around every test so one test's
    flags can never leak into another.
    """
    tbot = sys.modules["tbot"]
    old = tbot.flags
    tbot.flags = set()
    yield
    tbot.flags = old
