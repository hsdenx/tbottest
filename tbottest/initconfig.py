import ast
import atexit
import configparser
from configparser import ExtendedInterpolation
import tbot
import os
from tbottest.dynamicimport import get_boardmodule_import
from tbottest.dynamicimport import get_boardmodulepath_import
import tbottest.initconfighelper as inithelper

BOARDNAME = None


class _Singleton(type):
    """
    Metaclass making a class a per-process singleton: the first call to
    ClassName() constructs and caches the instance, every later call
    returns that same instance (and __init__ does not run again).

    Without this, every ClassName() call (e.g. one created inline
    inside a property that runs on every SSH connection attempt)
    re-parsed the same shared, UUID-suffixed ini file from scratch and
    registered its own weakref.finalize(self, self.cleanup) cleanup.
    Since that callback is a bound method of the instance itself, it
    keeps a strong reference back to it -- a documented
    weakref.finalize pitfall -- so none of these instances were ever
    actually garbage collected during the run; they just accumulated
    for as long as the process lived, each holding its own parsed
    configparser. A cached singleton with atexit-based cleanup avoids
    both the unbounded per-call leak and the repeated re-parsing.
    """

    _instances: dict = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


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
    except Exception:
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
    except Exception:
        pass
    # next common config
    value = cfgp.get("TC", name, fallback=default)
    if value == "None":
        return None
    return int(value)


def init_get_config_keys(
    cfgp: configparser.RawConfigParser,
    prefix: str,
) -> list:
    """
    returns the keys starting with prefix, from the sections
    init_get_config() searches.

    Keys of section "TC_BOARDNAME" come first, then those of section
    "TC", each key once, in the order of the ini file. Read their values
    with init_get_config(), so a key in "TC_BOARDNAME" hides the same key
    in "TC".

    :param cfgp: current config parser
    :param prefix: start of the key names
    """
    boardname = generic_get_boardname()
    keys = []
    for section in (f"TC_{boardname}", "TC"):
        if not cfgp.has_section(section):
            continue
        for key in cfgp.options(section):
            if key.startswith(prefix) and key not in keys:
                keys.append(key)
    return keys


# default of the init_*_config functions for a key that must be there
REQUIRED = object()


def init_section_get_config(
    cfgp: configparser.RawConfigParser,
    section: str,
    name: str,
    default=REQUIRED,
):
    """
    returns value of key name in section of the configparser, as it is
    written there (no conversion of "None").

    For the sections of tbot.ini outside the [TC] sections of the board
    ini, e.g. [BUILDHOST], [SSHMACHINE] or [PICOCOM_BOARDNAME].

    :param cfgp: current config parser
    :param section: name of the section
    :param name: name of key
    :param default: value if section or key is missing; without it a
        missing section or key raises RuntimeError
    """
    try:
        return cfgp.get(section, name)
    except (configparser.NoSectionError, configparser.NoOptionError):
        if default is REQUIRED:
            raise RuntimeError(f"key {name} missing in section [{section}]")
        return default


def init_config_to_bool(value: str) -> bool:
    """
    returns the boolean of an ini value, as configparser reads it
    (1, yes, true, on and 0, no, false, off, any case)

    :param value: value from the ini file
    """
    states = configparser.RawConfigParser.BOOLEAN_STATES
    if value.lower() not in states:
        raise ValueError(f"not a boolean: {value}")
    return states[value.lower()]


def init_section_get_config_bool(
    cfgp: configparser.RawConfigParser,
    section: str,
    name: str,
    default: bool,
) -> bool:
    """
    returns the boolean value of key name in section, see
    init_section_get_config() and init_config_to_bool()

    :param cfgp: current config parser
    :param section: name of the section
    :param name: name of key
    :param default: value if section or key is missing
    """
    value = init_section_get_config(cfgp, section, name, None)
    if value is None:
        return default
    return init_config_to_bool(value)


def init_get_config_bool(
    cfgp: configparser.RawConfigParser,
    name: str,
    default: bool,
) -> bool:
    """
    returns the boolean value of key name from the sections
    init_get_config() searches, see init_config_to_bool()

    :param cfgp: current config parser
    :param name: name of key
    :param default: value if the key is missing or "None"
    """
    value = init_get_config(cfgp, name, None)
    if value is None:
        return default
    return init_config_to_bool(value)


def init_read_inifile(filename: str) -> configparser.RawConfigParser:
    """
    returns a configparser with the ini file filename read, the way
    IniTBotConfig and IniConfig read theirs

    For code that has to read an ini file before IniTBotConfig and
    IniConfig exist, e.g. set_board_cfg() in boardspecific.py. Read its
    values with the init_*_config functions.

    :param filename: path of the ini file
    """
    cfgp = configparser.RawConfigParser(interpolation=ExtendedInterpolation())
    cfgp.read(filename)
    return cfgp


def init_has_section(cfgp: configparser.RawConfigParser, section: str) -> bool:
    """
    returns True if the configparser has section

    :param cfgp: current config parser
    :param section: name of the section
    """
    return cfgp.has_section(section)


def init_find_sections(cfgp: configparser.RawConfigParser, part: str) -> list:
    """
    returns the names of the sections that contain part, in the order of
    the ini file

    :param cfgp: current config parser
    :param part: part of the section name, e.g. "BUILDHOST"
    """
    return [s for s in cfgp.sections() if part in s]


def init_lab_get_config(
    cfgp: configparser.RawConfigParser,
    name: str,
    default=REQUIRED,
):
    """
    returns value of key name from configparser
    from section LABHOST or LABHOST_labname

    :param cfgp: current config parser
    :param name: name of key
    :param default: default value if key is not found; without it a
        missing key raises RuntimeError
    """
    sectionname = inithelper.get_lab_sectionname()
    return init_section_get_config(cfgp, sectionname, name, default)


def generic_get_boardname():
    """
    return the boards name in your lab setup

    setup the boardname through tbot.flag boardname, -f boardname:<NAME>

    You can overwrite this by defining your own board_set_boardname()
    in boardspecific.py if you need another approach.
    """
    global BOARDNAME

    if BOARDNAME is not None:
        return BOARDNAME

    if board_set_boardname is None:
        for f in tbot.flags:
            if f.startswith("boardname:"):
                BOARDNAME = f.split(":", 1)[1]
                return BOARDNAME
    else:
        BOARDNAME = board_set_boardname()
        return BOARDNAME

    raise RuntimeError(
        "please set your boardname with tbot.flag -f boardname:<NAME>"
    )


def bdi2000_poweron_cmds(cmds):
    """
    select the BDI2000 commands run after power on

    poweron_cmds in the BDI2000_<boardname> section of tbot.ini is either
    a list of commands, or a dictionary of named command lists. The tbot
    flag poweron_cmds:<name> selects an entry of the dictionary; without
    the flag the entry "default" is taken, if there is one.
    poweron_cmds:None runs no commands at all, the board control then does
    not talk to the BDI2000 after power on.

    :param cmds: poweron_cmds as read from tbot.ini, list or dictionary
    :returns: list of commands, empty if none are to be run
    """
    names = [
        f.split(":", 1)[1] for f in tbot.flags if f.startswith("poweron_cmds:")
    ]
    if len(names) > 1:
        raise RuntimeError(f"more than one flag poweron_cmds: {sorted(names)}")

    name = names[0] if names else None
    if name == "None":
        return []

    if isinstance(cmds, dict):
        if name is None:
            return list(cmds.get("default", []))
        if name not in cmds:
            raise RuntimeError(
                f"flag poweron_cmds:{name}: no such entry in poweron_cmds, "
                f"known are {sorted(cmds)} and None"
            )
        return list(cmds[name])

    if name is not None:
        raise RuntimeError(
            f"flag poweron_cmds:{name}: poweron_cmds is a list, not a "
            "dictionary of named lists; only poweron_cmds:None is possible"
        )
    return list(cmds)


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
except Exception:
    raise RuntimeError(
        f"Please define at least a dummy set_board_config in {get_boardmodulepath_import()}"
    )
    set_board_cfg = None


try:
    board_set_boardname = getattr(get_boardmodule_import(), "board_set_boardname")
except Exception:
    board_set_boardname = None


class IniTBotConfig(metaclass=_Singleton):
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
                except Exception:
                    self.ethdevices[nm] = devtmp

        self.bootmodecfg = {}
        for s in self.config_parser.sections():
            if "BOOTMODE" in s:
                nm = s.split("_")[1]
                modes = ast.literal_eval(self.config_parser.get(s, "modes"))
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
                self.dfuutilcfg[nm] = ast.literal_eval(cmds)

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
                xmodemcmd = ast.literal_eval(cmd)
                self.xmodemcfg[nm] = xmodemcmd
                self.xmodemdevice[nm] = self.config_parser.get(s, "device")

        self.lauterbachcfg = {}
        for s in self.config_parser.sections():
            if "LAUTERBACH_CONFIG" in s:
                nm = s.split("_")[2]

                try:
                    verbose = self.config_parser.get(s, "verbose")
                except Exception:
                    verbose = 1

                try:
                    ipath = self.config_parser.get(s, "install_path")
                except Exception:
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

                cmds = ast.literal_eval(self.config_parser.get(s, "cmds"))
                cfg = {
                    "cmds": cmds,
                }

                self.seggercfg[nm] = cfg

        self.bdi2000cfg = {}
        for s in self.config_parser.sections():
            if s.startswith("BDI2000_"):
                nm = s.split("_", 1)[1]
                try:
                    # list, or dictionary of named lists, see
                    # bdi2000_poweron_cmds()
                    cmds = ast.literal_eval(self.config_parser.get(s, "poweron_cmds"))
                except Exception:
                    cmds = []

                cfg = {
                    "ip": self.config_parser.get(s, "ip"),
                    "poweron_cmds": cmds,
                    "poweron_wait_state": self.config_parser.get(
                        s, "poweron_wait_state", fallback=None
                    ),
                    "poweron_timeout": float(
                        self.config_parser.get(s, "poweron_timeout", fallback="30")
                    ),
                }

                self.bdi2000cfg[nm] = cfg

        # the sections of the board's console and power control, by their
        # exact name <type>_<boardname>, as labgeneric.py reads them
        bn = generic_get_boardname()
        self.picocom = init_has_section(self.config_parser, f"PICOCOM_{bn}")
        self.kermit = init_has_section(self.config_parser, f"KERMIT_{bn}")
        self.scriptcom = init_has_section(self.config_parser, f"SCRIPTCOM_{bn}")
        self.telnet = init_has_section(self.config_parser, f"TELNET_{bn}")
        self.sispmctrl = init_has_section(self.config_parser, f"SISPMCTRL_{bn}")
        self.powershellscript = init_has_section(self.config_parser, f"POWERSHELLSCRIPT_{bn}")
        self.gpiopowerctrl = init_has_section(self.config_parser, f"GPIOPMCTRL_{bn}")
        self.tinkerforce = init_has_section(self.config_parser, f"TF_{bn}")
        self.tm021 = init_has_section(self.config_parser, f"TM021_{bn}")
        self.tbox = init_has_section(self.config_parser, f"TBOX_{bn}")
        self.tboxhwdaemon = init_has_section(self.config_parser, f"TBOX_HWDAEMON_{bn}")
        self.shelly = init_has_section(self.config_parser, f"SHELLY_{bn}")

        atexit.register(self.cleanup)

    def cleanup(self):
        if os.path.exists(self.tbotinifile):
            os.remove(self.tbotinifile)

    def get_section_config(self, section: str, name: str, default=REQUIRED):
        """
        returns value of key name in section of tbot.ini, see
        init_section_get_config()

        :param section: name of the section
        :param name: name of key
        :param default: value if missing; without it a missing key raises
        """
        return init_section_get_config(self.config_parser, section, name, default)

    def get_section_config_bool(self, section: str, name: str, default: bool) -> bool:
        """
        returns the boolean value of key name in section of tbot.ini, see
        init_section_get_config_bool()

        :param section: name of the section
        :param name: name of key
        :param default: value if missing
        """
        return init_section_get_config_bool(self.config_parser, section, name, default)

    def get_lab_config(self, name: str, default=REQUIRED):
        """
        returns value of key name in the section of the lab host, see
        init_lab_get_config()

        :param name: name of key
        :param default: value if missing; without it a missing key raises
        """
        return init_lab_get_config(self.config_parser, name, default)

    def has_section(self, section: str) -> bool:
        """
        returns True if tbot.ini has section

        :param section: name of the section
        """
        return init_has_section(self.config_parser, section)

    def find_sections(self, part: str) -> list:
        """
        returns the names of the sections of tbot.ini that contain part

        :param part: part of the section name
        """
        return init_find_sections(self.config_parser, part)


class IniConfig(metaclass=_Singleton):
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
        atexit.register(self.cleanup)

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

    def get_config_bool(self, name: str, default: bool) -> bool:
        """
        returns the boolean value of key name.

        use internal function init_get_config_bool

        :param name: name of key
        :param default: value if the key is missing or "None"
        """

        return init_get_config_bool(self.config_parser, name, default)

    def get_config_keys(self, prefix: str):
        """
        returns the keys starting with prefix.

        use internal function init_get_config_keys

        :param prefix: start of the key names
        """

        return init_get_config_keys(self.config_parser, prefix)

    def get_default_config(self, name: str, default: str):
        """
        return value of key from "default" section with name "name"

        :param name: name of key
        :param default: default value if key is not found
        """
        return init_get_default_config(self.config_parser, name, default)


FLAGS = {
    "boardname": (
        "boardname:<name> sets the name of the board, used when boardspecific.py "
        "does not define board_set_boardname()"
    ),
    "poweron_cmds": (
        "poweron_cmds:<name> selects the entry <name> of the dictionary "
        "poweron_cmds in the BDI2000_<boardname> section of tbot.ini; "
        "poweron_cmds:None runs no BDI2000 commands after power on"
    ),
    "boardfile": "boardfile:<path> board ini file, relative to the tbotconfig directory or absolute",
    "inifile": "inifile:<path> tbot.ini file, relative to the tbotconfig directory or absolute",
    "tmpfilepath": "tmpfilepath:<directory> where tbot writes its copies of tbot.ini and the board ini",
}
