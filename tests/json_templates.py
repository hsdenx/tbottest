"""
The JSON configuration templates of tbottest/tbotconfig/BOARDNAME as they
follow from the ini templates: the placeholders that boardspecific.py
fills at run time are values or expressions in JSON, those that
create_setup.sh fills stay. Used to make tbot.json and BOARDNAME.json and
by test_json_templates.py to keep them in step with the ini files.
"""

import ast
import configparser

RUNTIME = {
    "tbot.ini": {
        "@@TBOTBOARD@@": "${flag:boardname:-BOARDNAME}",
        "@@TBOTDATE@@": "20230406",
        "@@TFTPSUBDIR@@": "${board}/${date}",
    },
    "BOARDNAME.ini": {
        "@@USERNAME@@": "${env:USER}",
        "@@BUILDUSERNAME@@": "${env:USER}",
        "@@BUILDDOWNLOADSPATH@@": "please set in BOARDNAME.json",
        "@@BUILSTSTATEPATH@@": "please set in BOARDNAME.json",
        "@@TBOTDATE@@": "${lab:date}",
        "@@TBOTBOARD@@": "${lab:board}",
        "@@TBOTMACHINE@@": "CUSTOMER-board",
        "@@ROOTFSNAME@@": "${flag:rootfsname:-core-image-base}",
        "@@KASCONTAINER@@": "False",
        "@@TBOTSERVERIP@@": "${tbot:IPSETUP_BOARDNAME_eth0:serverip}",
        "@@TBOTIPADDR@@": "${tbot:IPSETUP_BOARDNAME_eth0:ipaddr}",
        "@@TBOTLABBASENFSPATH@@": "${lab:nfs_base_path}",
    },
}


def ini_to_json(path, runtime):
    """
    the JSON object of the ini template path, with the placeholders of
    runtime replaced; values that are a Python list or dictionary become
    JSON lists and objects
    """
    cp = configparser.RawConfigParser(interpolation=None)
    cp.read(path)
    data = {}
    for section in cp.sections():
        keys = {}
        for key in cp.options(section):
            value = cp.get(section, key)
            for placeholder, new in runtime.items():
                value = value.replace(placeholder, new)
            try:
                native = ast.literal_eval(value)
            except Exception:
                native = None
            keys[key] = native if isinstance(native, (list, dict)) else value
        data[section] = keys
    return data
