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
    for f in flags:
        if "inifile" in f:
            try:
                pathinifile = f.split(":")[1]
            except:
                raise RuntimeError("please use : as seperator inifile flag")

    workdir = os.getcwd()
    if pathinifile:
        if pathinifile[0] != r"\/":  # noqa: W605
            tbotinifile = workdir + "/" + pathinifile
        else:
            tbotinifile = pathinifile
    else:
        tbotinifile = workdir + "/../tbottest/tbotconfig/BOARDNAME/tbot.ini"

    uidfile = get_unique_filename_extension()
    newfilename = f"{tbotinifile}-{uidfile}"
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
    for f in flags:
        if "boardfile" in f:
            try:
                pathinifile = f.split(":")[1]
            except:
                raise RuntimeError("please use : as seperator boardfile flag")

    workdir = os.getcwd()
    if pathinifile:
        if pathinifile[0] != r"\/":  # noqa: W605
            filename = workdir + "/" + pathinifile
        else:
            filename = pathinifile
    else:
        filename = workdir + "/../tbottest/tbotconfig/BOARDNAME/BOARDNAME.ini"

    uidfile = get_unique_filename_extension()
    newfilename = f"{filename}-{uidfile}"
    initconfig.copy_file(filename, newfilename)
    TBOTBOARDNAME = newfilename
    return TBOTBOARDNAME
