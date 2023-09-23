import configparser
from configparser import ExtendedInterpolation
import tbot
import pathlib
import os
import sys

BOARDNAME = None
def generic_get_boardname():
    """
    return the boards name in your lab setup

    setup the boardname through tbot.flag selectableboardname

    You can overwrite this by defining your own board_set_boardname()
    in boardspecific.py if you need another approach.
    """
    global BOARDNAME

    if BOARDNAME != None:
        return BOARDNAME

    if board_set_boardname == None:
        for f in tbot.flags:
            if "selectableboardname" in f:
                BOARDNAME = f.split(":")[1]
                return BOARDNAME
    else:
        BOARDNAME = board_set_boardname()
        return BOARDNAME

    raise RuntimeError("please set your boardname with tbot.flag -f selectableboardname:<NAME>")

def copy_file(filename, newfile):
    fin = open(filename, "rt")
    data = fin.read()
    fin.close()
    fin = open(newfile, "wt")
    fin.write(data)
    fin.close()

def replace_in_file(filename, string, newv):
    fin = open(filename, "rt")
    data = fin.read()
    data = data.replace(string, newv)
    fin.close()
    fin = open(filename, "wt")
    fin.write(data)
    fin.close()

def find_in_file_and_append(filename, substring, append):
    with open(filename, 'r') as IN, open('output.txt', 'w') as OUT:
        for line in IN:
            if substring in line and append not in line:
                line = line.replace("\n", "")
                OUT.write(line + append + "\n")
            else:
                OUT.write(line)
    copy_file("output.txt", filename)

def find_in_file_and_delete(filename, substring):
    with open(filename, 'r') as IN, open('output.txt', 'w') as OUT:
        for line in IN:
            if substring not in line.strip("\n"):
                OUT.write(line)

    copy_file("output.txt", filename)

try:
    from tbotconfig.boardspecific import set_board_cfg
except:
    raise RuntimeError("Please define at least a dummy set_board_config in tbotconfig.boardspecific")
    set_board_cfg = None


try:
    from tbotconfig.boardspecific import board_set_boardname
except:
    board_set_boardname = None

class IniTBotConfig:
    """
    reads common tbot config
    """
    # may we pass an ini file path through tbot flags
    # with for example: -f inifile_/tmp/tbot.ini
    pathinifile = None
    for f in tbot.flags:
        if "inifile" in f:
            try:
                pathinifile = f.split(":")[1]
            except:
                raise RuntimeError(f"please use : as seperator inifile flag")

    config_parser = configparser.RawConfigParser(interpolation=ExtendedInterpolation())
    workdir = os.getcwd()
    if pathinifile:
        if pathinifile[0] != "\/":
            tbotinifile = workdir + "/" + pathinifile
        else:
            tbotinifile = pathinifile
    else:
        tbotinifile = workdir + f"/../tbottest/tbotconfig/{generic_get_boardname()}/tbot.ini"

    newfilename = tbotinifile + "-modified"
    copy_file(tbotinifile, newfilename)
    if set_board_cfg:
        set_board_cfg("IniTBotConfig", newfilename)
    replace_in_file(newfilename, "@@TBOTBOARD@@", generic_get_boardname())
    config_parser.read(newfilename)

    date = config_parser.get("LABHOST", "date")
    ethdevices = {}
    for s in config_parser.sections():
        if "IPSETUP" in s:
            nm = s.split("_")[1]
            dev = s.split("_")[2]

            ethaddr = config_parser.get(s, "ethaddr")
            labdevice = config_parser.get(s, "labdevice")
            ipaddr = config_parser.get(s, "ipaddr")
            serverip = config_parser.get(s, "serverip")
            netmask = config_parser.get(s, "netmask")

            cfg = {
                "labdevice": labdevice,
                "ethaddr": ethaddr,
                "serverip": serverip,
                "ipaddr": ipaddr,
                "netmask": netmask,
            }

            devtmp = {dev: cfg}
            try:
                tmpdict = ethdevices[nm]
                tmpdict.update({dev: cfg})
            except:  # noqa: E722
                ethdevices[nm] = devtmp

    bootmodecfg = {}
    for s in config_parser.sections():
        if "BOOTMODE" in s:
            nm = s.split("_")[1]
            modes = eval(config_parser.get(s, "modes"))
            bootmodecfg[nm] = modes

    ubcfg = {}
    for s in config_parser.sections():
        if "UBCFG" in s:
            nm = s.split("_")[1]
            cfg = {
                "ethintf": config_parser.get(s, "ethintf"),
            }

            ubcfg[nm] = cfg

    uuucfg = {}
    for s in config_parser.sections():
        if "UUU_CONFIG" in s:
            nm = s.split("_")[2]
            cmd = config_parser.get(s, "cmd")

            uuucmd = []
            for c in cmd.split(","):
                uuucmd.append(c)

            uuucfg[nm] = uuucmd

    lauterbachcfg = {}
    for s in config_parser.sections():
        if "LAUTERBACH_CONFIG" in s:
            nm = s.split("_")[2]

            try:
                verbose = config_parser.get(s, "verbose")
            except:
                verbose = 1

            try:
                ipath = config_parser.get(s, "install_path")
            except:
                ipath = "/opt/t32"

            cmd = config_parser.get(s, "cmd")
            conf = config_parser.get(s, "config")
            script = config_parser.get(s, "script")
            cfg = {
               "verbose" : verbose,
               "install_path" : ipath,
               "cmd": cmd,
               "config": conf,
               "script": script,
            }

            lauterbachcfg[nm] = cfg

    seggercfg = {}
    for s in config_parser.sections():
        if "SEGGER_CONFIG" in s:
            nm = s.split("_")[2]

            cmds = eval(config_parser.get(s, "cmds"))
            cfg = {
               "cmds": cmds,
            }

            seggercfg[nm] = cfg


class IniConfig:
    """
    reads board config
    """
    # read common tbot config and generate later [default] section
    cfg = IniTBotConfig()
    cfgp = cfg.config_parser

    # may we pass an ini file path through tbot flags
    # with for example: -f inifile_/tmp/tbot.ini
    pathinifile = None
    for f in tbot.flags:
        if "boardfile" in f:
            try:
                pathinifile = f.split(":")[1]
            except:
                raise RuntimeError(f"please use : as seperator boardfile flag")


    config_parser = configparser.RawConfigParser(interpolation=ExtendedInterpolation())
    workdir = os.getcwd()
    if pathinifile:
        if pathinifile[0] != "\/":  # noqa: W605
            filename = workdir + "/" + pathinifile
        else:
            filename = pathinifile
    else:
        filename = workdir + f"/../tbottest/tbotconfig/{generic_get_boardname()}/{generic_get_boardname()}.ini"

    newfilename = pathlib.Path(filename).parent.resolve()
    newfilename = newfilename / f"{os.path.basename(filename)}-modified"
    copy_file(filename, newfilename)
    if set_board_cfg:
        set_board_cfg("IniConfig", newfilename)
    config_parser.read(newfilename)
