"""
The JSON templates tbottest/tbotconfig/BOARDNAME/tbot.json and
BOARDNAME.json have to say what the ini templates say (see
json_templates.py): change both, or the test fails. And filled in as
create_setup.sh does, tbottest has to read them.
"""

import json
import os
import re

import pytest

from conftest import load_initconfig_functions
from json_templates import RUNTIME, ini_to_json

TEMPLATES = os.path.join(os.path.dirname(__file__), "..", "tbottest", "tbotconfig", "BOARDNAME")


@pytest.mark.parametrize("ini,js", [("tbot.ini", "tbot.json"), ("BOARDNAME.ini", "BOARDNAME.json")])
def test_json_template_follows_ini_template(ini, js):
    expected = ini_to_json(os.path.join(TEMPLATES, ini), RUNTIME[ini])
    with open(os.path.join(TEMPLATES, js)) as f:
        assert json.load(f) == expected


def filled(name, tmp_path):
    """the template with BOARDNAME and the placeholders of create_setup.sh
    replaced, written to tmp_path"""
    with open(os.path.join(TEMPLATES, name)) as f:
        text = f.read().replace("BOARDNAME", "foo")
    text = re.sub(r"@@[A-Z0-9_]+@@", "1", text)
    path = tmp_path / name.replace("BOARDNAME", "foo")
    path.write_text(text)
    return str(path)


def test_templates_read(tmp_path, monkeypatch):
    monkeypatch.setenv("USER", "tbotuser")
    ini = load_initconfig_functions(boardname="foo", labsection="LABHOST")
    tbotcfgp = ini.init_read_jsonfile(filled("tbot.json", tmp_path), [])
    assert tbotcfgp.get("LABHOST", "board") == "foo"
    assert tbotcfgp.get("LABHOST", "tftpsubdir") == "foo/20230406"
    board = ini.init_read_jsonfile(filled("BOARDNAME.json", tmp_path), ["rootfsname:x"], tbotcfgp)
    assert board.get("default", "user") == "tbotuser"
    assert board.get("default", "board") == "foo"
    assert board.get("default", "serverip") == tbotcfgp.get("IPSETUP_foo_eth0", "serverip")
    assert board.get("default", "rootfsname") == "x"
    nfs = tbotcfgp.get("LABHOST", "nfs_base_path")
    assert board.get("default", "nfs_path") == f"{nfs}/CUSTOMER-board/local"
