import tbot
import pathlib
import os


def inifile_get_tbotfilename():
    """
    helper function for setting up tbot.ini filename
    """
    # may we pass an ini file path through tbot flags
    # with for example: -f inifile_/tmp/tbot.ini
    pathinifile = None
    for f in tbot.flags:
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
    pathinifile = None
    for f in tbot.flags:
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



