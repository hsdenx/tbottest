"""
Unit tests for GenericLab.nfsboardbasedir() in tbottest/labgeneric.py.

labgeneric.py cannot be imported here (its module body resolves a real
lab and board environment), so the method's current source is taken out
of the class GenericLab with ast and run against stubs for
tbottest.boardgeneric and tbot's linux module.
"""

import ast
import os
import sys
import textwrap
import types

import pytest

LABGENERIC_PATH = os.path.join(
    os.path.dirname(__file__), "..", "tbottest", "labgeneric.py"
)


def load_method(classname, methodname):
    src = open(LABGENERIC_PATH).read()
    for node in ast.parse(src).body:
        if isinstance(node, ast.ClassDef) and node.name == classname:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == methodname:
                    def_src = textwrap.dedent(ast.get_source_segment(src, item, padded=True))
                    break
            else:
                continue
            break
    else:
        raise AssertionError(f"{classname}.{methodname} not found in {LABGENERIC_PATH}")

    linux = types.SimpleNamespace(
        Workdir=types.SimpleNamespace(static=lambda host, path: ("workdir", path))
    )
    ns = {"linux": linux}
    exec(compile(def_src, LABGENERIC_PATH, "exec"), ns)
    return ns[methodname]


class BoardConfig:
    def __init__(self, values):
        self.values = values

    def get_default_config(self, name, default):
        return self.values.get(name, default)


@pytest.fixture
def boardgeneric(monkeypatch):
    mod = types.ModuleType("tbottest.boardgeneric")
    monkeypatch.setitem(sys.modules, "tbottest.boardgeneric", mod)
    return mod


class Lab:
    # in GenericLab the method shadows the class attribute of the same
    # name, so self.nfsboardbasedir is the (true) bound method
    nfsboardbasedir = True


class TestNfsboardbasedir:
    def test_nfs_path_from_default_section(self, boardgeneric):
        boardgeneric.cfggeneric = BoardConfig({"nfs_path": "/srv/nfs/abb/amc-tqm855m"})
        nfsboardbasedir = load_method("GenericLab", "nfsboardbasedir")
        assert nfsboardbasedir(Lab()) == ("workdir", "/srv/nfs/abb/amc-tqm855m")

    def test_nfs_path_missing(self, boardgeneric):
        boardgeneric.cfggeneric = BoardConfig({})
        nfsboardbasedir = load_method("GenericLab", "nfsboardbasedir")
        with pytest.raises(RuntimeError, match="nfs_path missing"):
            nfsboardbasedir(Lab())
