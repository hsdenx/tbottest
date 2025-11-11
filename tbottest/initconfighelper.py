import argparse
import tbot
import os
import sys
from tbot.newbot import build_parser
import tbottest.initconfig as initconfig
import uuid


def get_lab_sectionname() -> str:
    for f in tbot.flags:
        if "labname" in f:
            sn = f.split(":")[1]
            sn = f"LABHOST_{sn}"
            return sn
    return "LABHOST"


def get_tbot_arguments():
    """
    get the arguments with which tbot is called
    """
    if "sphinx-build" in sys.argv[0]:
        sys.argv = sys.argv[:1]

    if "newbot" in sys.argv[0]:
        sys.argv = sys.argv[1:]

    parser = build_parser()
    parser.add_argument("--complete-module", help=argparse.SUPPRESS)
    parser.add_argument("--complete-testcase", help=argparse.SUPPRESS)
    arguments = sys.argv.copy()
    if "pytest" in sys.argv[0]:
        arguments = arguments[1:]
        i = 0
        while i < len(arguments):
            argv = arguments[i]
            if "@" not in argv:
                arguments.remove(argv)
            else:
                i += 1

    try:
        args = parser.parse_args(arguments)
    except Exception as error:
        print("get_tbot_arguments error parsing arguments: ", error)

    # in case we do autocompletion, supress output
    if args.complete_testcase is not None:
        tbot.selectable.printed = True
    if args.complete_module is not None:
        tbot.selectable.printed = True
    return args


def get_tbot_flags():
    if "--usetbotflags" in sys.argv:
        return tbot.flags

    args = get_tbot_arguments()
    return args.flags


UUID_FILENAME = None


def get_unique_filename_extension():
    global UUID_FILENAME
    if UUID_FILENAME is not None:
        return UUID_FILENAME

    UUID_FILENAME = str(uuid.uuid4())
    return UUID_FILENAME

TBOTCONFIGPATH = None

def get_tbotconfig_path():
    global TBOTCONFIGPATH
    if TBOTCONFIGPATH is not None:
        return TBOTCONFIGPATH

    try:
        TBOTCONFIGPATH = os.environ['TBOTCONFIGPATH']
        return TBOTCONFIGPATH
    except:
        pass

    try:
        for p in os.environ['PYTHONPATH'].split(":"):
            if "tbotconfig" in p:
                TBOTCONFIGPATH = p.replace("tbotconfig", "")
                return TBOTCONFIGPATH
    except:
        pass

    TBOTCONFIGPATH = os.getcwd()
    return TBOTCONFIGPATH

TBOTINIFILE = None


def inifile_get_tbotfilename():
    """
    helper function for setting up tbot.ini filename
    """
    global TBOTINIFILE
    if TBOTINIFILE is not None:
        return TBOTINIFILE

    # may we pass an ini file path through tbot flags
    # with for example: -f inifile_/tmp/tbot.ini
    flags = get_tbot_flags()
    pathinifile = None
    tmppath = None
    for f in flags:
        if "inifile" in f:
            try:
                pathinifile = f.split(":")[1]
            except:
                raise RuntimeError("please use : as seperator inifile flag")
        if "tmpfilepath" in f:
            tmppath = f.split(":")[1]

    cfgpath = get_tbotconfig_path()

    if pathinifile:
        if pathinifile[0] != r"\/":  # noqa: W605
            tbotinifile = cfgpath + "/" + pathinifile
        else:
            tbotinifile = pathinifile
    else:
        tbotinifile = cfgpath + "/../tbottest/tbotconfig/BOARDNAME/tbot.ini"

    uidfile = get_unique_filename_extension()
    newfilename = f"{tbotinifile}-{uidfile}"
    if tmppath:
        name = os.path.basename(tbotinifile)
        newfilename = f"{tmppath}/{name}-{uidfile}"

    initconfig.copy_file(tbotinifile, newfilename)
    TBOTINIFILE = newfilename
    return TBOTINIFILE


TBOTBOARDNAME = None


def inifile_get_tbotboardfilename():
    """
    helper function for setting up boardname.ini filename
    """
    global TBOTBOARDNAME
    if TBOTBOARDNAME is not None:
        return TBOTBOARDNAME

    # may we pass an ini file path through tbot flags
    # with for example: -f inifile_/tmp/boardname.ini
    flags = get_tbot_flags()
    pathinifile = None
    tmppath = None
    for f in flags:
        if "boardfile" in f:
            try:
                pathinifile = f.split(":")[1]
            except:
                raise RuntimeError("please use : as seperator boardfile flag")
        if "tmpfilepath" in f:
            tmppath = f.split(":")[1]

    cfgpath = get_tbotconfig_path()

    if pathinifile:
        if pathinifile[0] != r"\/":  # noqa: W605
            filename = cfgpath + "/" + pathinifile
        else:
            filename = pathinifile
    else:
        filename = cfgpath + "/../tbottest/tbotconfig/BOARDNAME/BOARDNAME.ini"

    uidfile = get_unique_filename_extension()
    newfilename = f"{filename}-{uidfile}"
    if tmppath:
        name = os.path.basename(filename)
        newfilename = f"{tmppath}/{name}-{uidfile}"

    initconfig.copy_file(filename, newfilename)
    TBOTBOARDNAME = newfilename
    return TBOTBOARDNAME
