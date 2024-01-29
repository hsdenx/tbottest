import argparse
import tbot
import pathlib
import os
import sys
from tbot.newbot import build_parser

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
    parser = build_parser()
    parser.add_argument("--complete-module", help=argparse.SUPPRESS)
    parser.add_argument("--complete-testcase", help=argparse.SUPPRESS)
    try:
        args = parser.parse_args(sys.argv)
    except Exception as error:
        print("get_tbot_arguments error parsing arguments: ", error)

    # in case we do autocompletion, supress output
    if args.complete_testcase != None:
        tbot.selectable.printed = True
    if args.complete_module != None:
        tbot.selectable.printed = True
    return args


def get_tbot_flags():
    args = get_tbot_arguments()
    return args.flags


def inifile_get_tbotfilename():
    """
    helper function for setting up tbot.ini filename
    """
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
        if pathinifile[0] != "\/":  # noqa: W605
            tbotinifile = workdir + "/" + pathinifile
        else:
            tbotinifile = pathinifile
    else:
        tbotinifile = (
             workdir + f"/../tbottest/tbotconfig/BOARDNAME/tbot.ini"
        )

    return tbotinifile


def inifile_get_tbotboardfilename():
    """
    helper function for setting up boardname.ini filename
    """
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
        if pathinifile[0] != "\/":  # noqa: W605
            filename = workdir + "/" + pathinifile
        else:
            filename = pathinifile
    else:
        filename = (
             workdir
             + f"/../tbottest/tbotconfig/BOARDNAME/BOARDNAME.ini"
         )

    return filename



