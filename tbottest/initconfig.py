import configparser
from configparser import ExtendedInterpolation
import tbot
import pathlib
import os
import tbottest.initconfighelper as inithelper
import uuid

BOARDNAME = None

unique_filename_extension = str(uuid.uuid4())


def init_get_config(
    cfgp: configparser.RawConfigParser,
    name: str,
    default: str,
) -> str:
    """
    returns value of key name from configparser.

    Searches first for a "TC_BOARDNAME" section and if it there
    is not the key, search in section "TC". If not found, return
    default value. If default value is "None" return None

    :param cfgp: current config parser
    :param name: name of key
    :param default: default value if key is not found
    """
    boardname = generic_get_boardname()
    # first try boardname specific config
    try:
        value = cfgp.get(f"TC_{boardname}", name)
        return value
    except:
        pass
    # next common config
    value = cfgp.get("TC", name, fallback=default)
    if value == "None":
        return None
    return value


def init_lab_get_config(
    cfgp: configparser.RawConfigParser,
    name: str,
    default: str,
) -> str:
    """
    returns value of key name from configparser
    from section LABHOST or LABHOST_labname

    :param cfgp: current config parser
    :param name: name of key
    :param default: default value if key is not found
    """
    sectionname = inithelper.get_lab_sectionname()
    # first try boardname specific config
    try:
        value = cfgp.get(sectionname, name)
        return value
    except:
        pass

    return default


def generic_get_boardname():
    """
    return the boards name in your lab setup

    setup the boardname through tbot.flag selectableboardname

    You can overwrite this by defining your own board_set_boardname()
    in boardspecific.py if you need another approach.
    """
    global BOARDNAME

    if BOARDNAME is not None:
        return BOARDNAME

    if board_set_boardname is None:
        for f in tbot.flags:
            if "selectableboardname" in f:
                BOARDNAME = f.split(":")[1]
                return BOARDNAME
    else:
        BOARDNAME = board_set_boardname()
        return BOARDNAME

    raise RuntimeError(
        "please set your boardname with tbot.flag -f selectableboardname:<NAME>"
    )


def copy_file(filename, newfile):
    """
    copy file filename to newfile

    :param filename: full path and name of source file
    :param newfile: full path and name of target file
    """
    fin = open(filename, "rt")
    data = fin.read()
    fin.close()
    fin = open(newfile, "wt")
    fin.write(data)
    fin.close()


def replace_in_file(filename, string, newv):
    """
    replace string in filename with string newv

    :param filename: full path and name of source file
    :param string: searchstring
    :param newv: new value
    """
    fin = open(filename, "rt")
    data = fin.read()
    data = data.replace(string, newv)
    fin.close()
    fin = open(filename, "wt")
    fin.write(data)
    fin.close()


def find_in_file_and_append(filename, substring, append):
    """
    append in file filename to the string substring the string append

    :param filename: full path and name of source file
    :param substring: string to which string append gets appended
    :param append: appended string
    """
    with open(filename, "r") as IN, open("output.txt", "w") as OUT:
        for line in IN:
            if substring in line and append not in line:
                line = line.replace("\n", "")
                OUT.write(line + append + "\n")
            else:
                OUT.write(line)
    copy_file("output.txt", filename)


def find_in_file_and_delete(filename, substring):
    """
    delete line in file filename when substring is found

    :param filename: full path and name of source file
    :param substring: substring which get searched
    """
    with open(filename, "r") as IN, open("output.txt", "w") as OUT:
        for line in IN:
            if substring not in line.strip("\n"):
                OUT.write(line)

    copy_file("output.txt", filename)


try:
    from tbotconfig.boardspecific import set_board_cfg
except:
    raise RuntimeError(
        "Please define at least a dummy set_board_config in tbotconfig.boardspecific"
    )
    set_board_cfg = None


try:
    from tbotconfig.boardspecific import board_set_boardname
except:
    board_set_boardname = None


class IniTBotConfig:
    """
    reads common tbot config

    see: :ref:`boardspecificruntimeadaption`
    """

    workdir = os.getcwd()
    tbotinifile = inithelper.inifile_get_tbotfilename()
    labsectionname = inithelper.get_lab_sectionname()
    newfilename = tbotinifile + f"-{unique_filename_extension}"
    tbot.log.message(tbot.log.c(f"IniTBotConfig: use {newfilename}").yellow)
    copy_file(tbotinifile, newfilename)
    if set_board_cfg:
        set_board_cfg("IniTBotConfig", newfilename)
    replace_in_file(newfilename, "@@TBOTBOARD@@", generic_get_boardname())
    config_parser = configparser.RawConfigParser(interpolation=ExtendedInterpolation())
    config_parser.read(newfilename)

    date = config_parser.get(labsectionname, "date")
    shelltype = init_lab_get_config(config_parser, "shelltype", "ash")
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
                "verbose": verbose,
                "install_path": ipath,
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

    see: :ref:`boardspecificruntimeadaption`
    """

    # read common tbot config and generate later [default] section
    cfg = IniTBotConfig()
    cfgp = cfg.config_parser
    workdir = os.getcwd()

    filename = inithelper.inifile_get_tbotboardfilename()
    newfilename = pathlib.Path(filename).parent.resolve()
    newfilename = (
        newfilename / f"{os.path.basename(filename)}-{unique_filename_extension}"
    )
    tbot.log.message(tbot.log.c(f"IniConfig: use {newfilename}").yellow)
    copy_file(filename, newfilename)
    if set_board_cfg:
        set_board_cfg("IniConfig", newfilename)

    config_parser = configparser.RawConfigParser(interpolation=ExtendedInterpolation())
    config_parser.read(newfilename)
