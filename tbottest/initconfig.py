import configparser
from configparser import ExtendedInterpolation
import tbot
import os
import weakref
from tbottest.dynamicimport import get_boardmodule_import
from tbottest.dynamicimport import get_boardmodulepath_import
import tbottest.initconfighelper as inithelper

BOARDNAME = None


def init_get_default_config(
    cfgp: configparser.RawConfigParser,
    name: str,
    default: str,
) -> str:
    """
    returns value of key name from configparser.

    Searches key name in "default" sectio

    :param cfgp: current config parser
    :param name: name of key
    :param default: default value if key is not found
    """
    value = cfgp.get("default", name, fallback=default)
    if value == "None":
        return None
    return value


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
        if value == "None":
            return None
        return value
    except:
        pass
    # next common config
    value = cfgp.get("TC", name, fallback=default)
    if value == "None":
        return None
    return value


def init_get_config_int(
    cfgp: configparser.RawConfigParser,
    name: str,
    default: str,
) -> int:
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
        if value == "None":
            return None
        return int(value)
    except:
        pass
    # next common config
    value = cfgp.get("TC", name, fallback=default)
    if value == "None":
        return None
    return int(value)


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
    set_board_cfg = getattr(get_boardmodule_import(), "set_board_cfg")
except:
    raise RuntimeError(
        f"Please define at least a dummy set_board_config in {get_boardmodulepath_import()}"
    )
    set_board_cfg = None


try:
    board_set_boardname = getattr(get_boardmodule_import(), "board_set_boardname")
except:
    board_set_boardname = None


class IniTBotConfig:
    """
    reads common tbot config

    see: :ref:`boardspecificruntimeadaption`
    """

    # must be done before init
    tbotinifile = inithelper.inifile_get_tbotfilename()
    if set_board_cfg:
        set_board_cfg("IniTBotConfig", tbotinifile)
    replace_in_file(tbotinifile, "@@TBOTBOARD@@", generic_get_boardname())

    def __init__(self):
        self.tbotinifile = inithelper.inifile_get_tbotfilename()
        self.labsectionname = inithelper.get_lab_sectionname()
        self.workdir = os.getcwd()
        self.config_parser = configparser.RawConfigParser(
            interpolation=ExtendedInterpolation()
        )
        self.config_parser.read(self.tbotinifile)
        self.date = self.config_parser.get(self.labsectionname, "date")
        self.shelltype = init_lab_get_config(self.config_parser, "shelltype", "ash")
        self.shelltype = self.shelltype.lower()
        self.ethdevices = {}
        self.picocom = False
        self.kermit = False
        self.scriptcom = False
        self.sispmctrl = False
        self.powershellscript = False
        self.gpiopowerctrl = False
        self.tinkerforce = False
        self.tm021 = False
        for s in self.config_parser.sections():
            if "IPSETUP" in s:
                nm = s.split("_")[1]
                dev = s.split("_")[2]

                ethaddr = self.config_parser.get(s, "ethaddr")
                labdevice = self.config_parser.get(s, "labdevice")
                ipaddr = self.config_parser.get(s, "ipaddr")
                serverip = self.config_parser.get(s, "serverip")
                netmask = self.config_parser.get(s, "netmask")

                cfg = {
                    "labdevice": labdevice,
                    "ethaddr": ethaddr,
                    "serverip": serverip,
                    "ipaddr": ipaddr,
                    "netmask": netmask,
                }

                devtmp = {dev: cfg}
                try:
                    tmpdict = self.ethdevices[nm]
                    tmpdict.update({dev: cfg})
                except:  # noqa: E722
                    self.ethdevices[nm] = devtmp

        self.bootmodecfg = {}
        for s in self.config_parser.sections():
            if "BOOTMODE" in s:
                nm = s.split("_")[1]
                modes = eval(self.config_parser.get(s, "modes"))
                self.bootmodecfg[nm] = modes

        self.ubcfg = {}
        for s in self.config_parser.sections():
            if "UBCFG" in s:
                nm = s.split("_")[1]
                cfg = {
                    "ethintf": self.config_parser.get(s, "ethintf"),
                }

                self.ubcfg[nm] = cfg

        self.dfuutilcfg = {}
        for s in self.config_parser.sections():
            if "DFUUTIL_CONFIG" in s:
                nm = s.split("_")[2]
                cmds = self.config_parser.get(s, "cmds")
                self.dfuutilcfg[nm] = eval(cmds)

        self.uuucfg = {}
        for s in self.config_parser.sections():
            if "UUU_CONFIG" in s:
                nm = s.split("_")[2]
                cmd = self.config_parser.get(s, "cmd")

                uuucmd = []
                for c in cmd.split(","):
                    uuucmd.append(c.strip())

                self.uuucfg[nm] = uuucmd

        self.xmodemcfg = {}
        self.xmodemdevice = {}
        for s in self.config_parser.sections():
            if "XMODEM_CONFIG" in s:
                nm = s.split("_")[2]
                cmd = self.config_parser.get(s, "cmd")
                xmodemcmd = eval(cmd)
                self.xmodemcfg[nm] = xmodemcmd
                self.xmodemdevice[nm] = self.config_parser.get(s, "device")

        self.lauterbachcfg = {}
        for s in self.config_parser.sections():
            if "LAUTERBACH_CONFIG" in s:
                nm = s.split("_")[2]

                try:
                    verbose = self.config_parser.get(s, "verbose")
                except:
                    verbose = 1

                try:
                    ipath = self.config_parser.get(s, "install_path")
                except:
                    ipath = "/opt/t32"

                cmd = self.config_parser.get(s, "cmd")
                conf = self.config_parser.get(s, "config")
                script = self.config_parser.get(s, "script")
                cfg = {
                    "verbose": verbose,
                    "install_path": ipath,
                    "cmd": cmd,
                    "config": conf,
                    "script": script,
                }

                self.lauterbachcfg[nm] = cfg

        self.seggercfg = {}
        for s in self.config_parser.sections():
            if "SEGGER_CONFIG" in s:
                nm = s.split("_")[2]

                cmds = eval(self.config_parser.get(s, "cmds"))
                cfg = {
                    "cmds": cmds,
                }

                self.seggercfg[nm] = cfg

        bn = generic_get_boardname()
        for s in self.config_parser.sections():
            if f"PICOCOM_{bn}" in s:
                self.picocom = True
            if f"KERMIT_{bn}" in s:
                self.kermit = True
            if f"SCRIPTCOM_{bn}" in s:
                self.scriptcom = True
            if f"SISPMCTRL_{bn}" in s:
                self.sispmctrl = True
            if f"POWERSHELLSCRIPT_{bn}" in s:
                self.powershellscript = True
            if f"GPIOPMCTRL_{bn}" in s:
                self.gpiopowerctrl = True
            if f"TF_{bn}" in s:
                self.tinkerforce = True
            if f"TM021_{bn}" in s:
                self.tm021 = True

        weakref.finalize(self, self.cleanup)

    def cleanup(self):
        if os.path.exists(self.tbotinifile):
            os.remove(self.tbotinifile)


class IniConfig:
    """
    reads board config

    see: :ref:`boardspecificruntimeadaption`
    """

    # read common tbot config and generate later [default] section
    # cfg = IniTBotConfig()
    # cfgp = cfg.config_parser

    if set_board_cfg:
        set_board_cfg("IniConfig", inithelper.inifile_get_tbotboardfilename())

    def __init__(self):
        self.workdir = os.getcwd()
        self.config_parser = configparser.RawConfigParser(
            interpolation=ExtendedInterpolation()
        )
        self.filename = inithelper.inifile_get_tbotboardfilename()
        self.config_parser.read(self.filename)
        weakref.finalize(self, self.cleanup)

    def cleanup(self):
        if os.path.exists(self.filename):
            os.remove(self.filename)

    def get_config(self, name: str, default: str):
        """
        returns value of key name from configparser.

        use internal function init_get_config

        :param name: name of key
        :param default: default value if key is not found
        """

        return init_get_config(self.config_parser, name, default)

    def get_config_int(self, name: str, default: str):
        """
        returns int value of key name from configparser.

        use internal function init_get_config_int

        :param name: name of key
        :param default: default value if key is not found
        """

        return init_get_config_int(self.config_parser, name, default)

    def get_default_config(self, name: str, default: str):
        """
        return value of key from "default" section with name "name"

        :param name: name of key
        :param default: default value if key is not found
        """
        return init_get_default_config(self.config_parser, name, default)
