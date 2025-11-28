import configparser
from configparser import ExtendedInterpolation

import tbot

from tbottest.initconfig import generic_get_boardname
from tbottest.initconfig import replace_in_file
from tbottest.initconfig import find_in_file_and_delete

TBOTFILE = None
SERVERIP = None


def BOARDNAME_get_lab_serverip(filename: str = None):
    """
    helper to save ini file reads
    """
    global SERVERIP

    if SERVERIP is not None:
        return SERVERIP

    if filename is None:
        raise RuntimeError("serverip not setup")

    # read from ini file
    config_parser = configparser.RawConfigParser(interpolation=ExtendedInterpolation())
    config_parser.read(filename)
    for s in config_parser.sections():
        if "IPSETUP" in s:
            nm = s.split("_")[1]
            dev = s.split("_")[2]

            if nm == generic_get_boardname() and dev == "eth0":
                SERVERIP = config_parser.get(s, "serverip")
                return SERVERIP

    raise RuntimeError("serverip setup not found")


IPADDR = None


def BOARDNAME_get_board_ipaddr(filename: str = None):
    """
    helper to save ini file reads
    """
    global IPADDR

    if IPADDR is not None:
        return IPADDR

    if filename is None:
        raise RuntimeError("ipaddr not setup")

    # read from ini file
    config_parser = configparser.RawConfigParser(interpolation=ExtendedInterpolation())
    config_parser.read(filename)
    for s in config_parser.sections():
        if "IPSETUP" in s:
            nm = s.split("_")[1]
            dev = s.split("_")[2]

            if nm == generic_get_boardname() and dev == "eth0":
                IPADDR = config_parser.get(s, "ipaddr")
                return IPADDR

    raise RuntimeError("ipaddr not found")


def board_set_boardname() -> str:
    """
    sample implementation as example how to set own boardname

    This name is used for selecting the sections in the ini files

    So you can have in one lab setup more than one boards
    """
    # do not use selectableboardname flag
    print("SET BOARDNAME to BOARDNAME (This is only useful for documentation build!")
    BOARDNAME = "BOARDNAME"
    for f in tbot.flags:
        if "8G" in f:
            if len(f) == 2:
                BOARDNAME = "BOARDNAME8g"

    return BOARDNAME


ROOTFSNAME = None


def BOARDNAME_get_rootfsname():
    """
    helper to save ini file reads
    """
    global ROOTFSNAME

    if ROOTFSNAME is not None:
        return ROOTFSNAME

    for f in tbot.flags:
        if "rootfsname" in f:
            ROOTFSNAME = f.split(":")[1]
            return ROOTFSNAME

    ROOTFSNAME = "core-image-base"
    return ROOTFSNAME


MACHINENAME = None


def BOARDNAME_get_machinename():
    """
    helper to save ini file reads
    """
    global MACHINENAME

    if MACHINENAME is not None:
        return MACHINENAME

    MACHINENAME = "CUSTOMER-board"
    return MACHINENAME


def print_log(msg):
    try:
        if tbot.selectable.printed:
            return
    except:
        pass

    tbot.log.message(tbot.log.c(msg).yellow)


def set_ub_board_specific(self):  # noqa: C901
    """
    sample implementation for U-Boot setup dependent on tbot.flags
    """
    if "silent" in tbot.flags:
        self.env("console", "silent")


def set_board_cfg(temp: str = None, filename: str = None):  # noqa: C901
    """
    setup board specific stuff in ini files before they get parsed
    """
    # print big fat warning, that example is used
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    print("You use example implementation of boardspecific.py")
    print("You really should use your own implementation, as it is example only")
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    print_log(f"TBOT.FLAGS {sorted(tbot.flags)}")

    if "tbot.ini" in str(filename):
        global TBOTFILE

        TBOTFILE = filename

    replace_in_file(filename, "@@USERNAME@@", "please set in boardspecific.py")
    # Should come from selected build section, ToDo
    replace_in_file(filename, "@@BUILDUSERNAME@@", "please set in boardspecific.py")
    replace_in_file(filename, "@@BUILDDOWNLOADSPATH@@", "please set in boardspecific.py")
    replace_in_file(filename, "@@BUILSTSTATEPATH@@", "please set in boardspecific.py")
    replace_in_file(filename, "@@TBOTDATE@@", "20230406")
    replace_in_file(filename, "@@TBOTMACHINE@@", BOARDNAME_get_machinename())
    boardname = generic_get_boardname()
    print_log(f"boardname now {boardname}")

    kascontainer = "False"
    sshkeypath = None
    kasfilename = "please set in boardspecifc.py your yml file"
    tftpsubdir = "${board}/${date}"
    replace_in_file(filename, "@@TBOTBOARD@@", boardname)
    replace_in_file(filename, "@@TFTPSUBDIR@@", tftpsubdir)
    tmp = BOARDNAME_get_rootfsname()
    replace_in_file(filename, "@@ROOTFSNAME@@", tmp)
    print_log(f"Using kas file {kasfilename}")
    replace_in_file(filename, "@@KASFILENAME@@", kasfilename)
    replace_in_file(filename, "@@KASCONTAINER@@", kascontainer)
    if sshkeypath:
        replace_in_file(filename, "/home/hs/.ssh", sshkeypath)

    replace_in_file(filename, "@@TBOTSERVERIP@@", BOARDNAME_get_lab_serverip(filename))
    replace_in_file(filename, "@@TBOTIPADDR@@", BOARDNAME_get_board_ipaddr(filename))

    # only for creating docs!
    replace_in_file(filename, "@@PICOCOMDELAY@@", "3")

    # replace in board file setttings from tbot.ini
    if "tbot.ini" not in str(filename):
        config_parser = configparser.RawConfigParser(
            interpolation=ExtendedInterpolation()
        )
        config_parser.read(TBOTFILE)
        for s in config_parser.sections():
            if "LABHOST" in s:
                try:
                    basepath = config_parser.get(s, "nfs_base_path")
                except:
                    raise RuntimeError(
                        f"Could not find 'nfs_base_path' key in section 'default' in {filename}"
                    )
        replace_in_file(filename, "@@TBOTLABBASENFSPATH@@", basepath)


FLAGS = {
    "selectableboardname": "set value of tbot.selectable.boardname format selectableboardname:<name>",
}
