import argparse
import tbot
import os
import sys
from tbot.newbot import build_parser
import tbottest.initconfig as initconfig
import uuid


def get_lab_sectionname() -> str:
    """
    returns the name of the section of the lab host in tbot.ini

    LABHOST_<name> with the tbot flag labname:<name>, else LABHOST.
    """
    for f in tbot.flags:
        if "labname" in f:
            sn = f.split(":")[1]
            sn = f"LABHOST_{sn}"
            return sn
    return "LABHOST"


def get_tbot_arguments():
    """
    get the arguments with which tbot is called

    Parses sys.argv with the argument parser of tbot
    (tbot.newbot.build_parser()), plus the options --complete-module and
    --complete-testcase of the shell completion, which also suppress the
    output of tbot. Under sphinx-build no arguments are parsed, under
    pytest only the argument files (@<file>).

    :returns: the parsed arguments (argparse.Namespace)
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
        raise RuntimeError(f"get_tbot_arguments error parsing arguments: {error}") from error

    # in case we do autocompletion, supress output
    if args.complete_testcase is not None:
        tbot.selectable.printed = True
    if args.complete_module is not None:
        tbot.selectable.printed = True
    return args


def get_tbot_flags():
    """
    returns the tbot flags the ini files are set up with

    The flags of the command line (get_tbot_arguments()), or tbot.flags if
    sys.argv contains --usetbotflags, as Documentation/conf.py sets it for
    the documentation build.
    """
    if "--usetbotflags" in sys.argv:
        return tbot.flags

    args = get_tbot_arguments()
    return args.flags


UUID_FILENAME = None


def get_unique_filename_extension():
    """
    returns the extension of the copies of the ini files of this run

    A random uuid4 string, made on the first call; tbot.ini and the board
    ini of one run get the same one.
    """
    global UUID_FILENAME
    if UUID_FILENAME is not None:
        return UUID_FILENAME

    UUID_FILENAME = str(uuid.uuid4())
    return UUID_FILENAME


TBOTCONFIGPATH = None


def get_tbotconfig_path():
    """
    returns the directory relative paths of the ini files start from

    The environment variable TBOTCONFIGPATH, else the first entry of
    PYTHONPATH that contains "tbotconfig", with "tbotconfig" removed, else
    the current directory. Decided on the first call.
    """
    global TBOTCONFIGPATH
    if TBOTCONFIGPATH is not None:
        return TBOTCONFIGPATH

    try:
        TBOTCONFIGPATH = os.environ['TBOTCONFIGPATH']
        return TBOTCONFIGPATH
    except Exception:
        pass

    try:
        for p in os.environ['PYTHONPATH'].split(":"):
            if "tbotconfig" in p:
                TBOTCONFIGPATH = p.replace("tbotconfig", "")
                return TBOTCONFIGPATH
    except Exception:
        pass

    TBOTCONFIGPATH = os.getcwd()
    return TBOTCONFIGPATH


_INIFILE_CACHE: dict = {}


def _get_cached_inifile(cachekey: str, flagkey: str, default_filename: str, errmsg: str) -> str:
    if cachekey in _INIFILE_CACHE:
        return _INIFILE_CACHE[cachekey]

    # may we pass an ini file path through tbot flags
    # with for example: -f inifile:/tmp/tbot.ini
    flags = get_tbot_flags()
    pathinifile = None
    tmppath = None
    for f in flags:
        if flagkey in f:
            try:
                pathinifile = f.split(":")[1]
            except Exception:
                raise RuntimeError(errmsg)
        if "tmpfilepath" in f:
            tmppath = f.split(":")[1]

    cfgpath = get_tbotconfig_path()

    if pathinifile:
        if pathinifile[0] != "/":
            filename = cfgpath + "/" + pathinifile
        else:
            filename = pathinifile
    else:
        filename = cfgpath + "/../tbottest/tbotconfig/BOARDNAME/" + default_filename

    uidfile = get_unique_filename_extension()
    newfilename = f"{filename}-{uidfile}"
    if tmppath:
        name = os.path.basename(filename)
        newfilename = f"{tmppath}/{name}-{uidfile}"

    initconfig.copy_file(filename, newfilename)
    _INIFILE_CACHE[cachekey] = newfilename
    return newfilename


def inifile_get_tbotfilename():
    """
    returns the path of the copy of tbot.ini this run uses

    The file is the one of the tbot flag inifile:<path>, relative to
    get_tbotconfig_path() or absolute, else the template
    tbottest/tbotconfig/BOARDNAME/tbot.ini. tbot copies it on the first
    call, to <file>-<id> or, with the flag tmpfilepath:<dir>, into <dir>
    (id from get_unique_filename_extension()), and works on the copy;
    set_board_cfg() of boardspecific.py replaces the placeholders there.
    """
    return _get_cached_inifile(
        "tbotinifile", "inifile", "tbot.ini", "please use : as seperator inifile flag"
    )


def inifile_get_tbotboardfilename():
    """
    returns the path of the copy of the board ini this run uses

    As inifile_get_tbotfilename(), with the tbot flag boardfile:<path> and
    the template tbottest/tbotconfig/BOARDNAME/BOARDNAME.ini.
    """
    return _get_cached_inifile(
        "tbotboardname",
        "boardfile",
        "BOARDNAME.ini",
        "please use : as seperator boardfile flag",
    )
