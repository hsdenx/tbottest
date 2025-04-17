import importlib
import os
import tbot

IMPORTPATH = None
BOARDMODULE = None
BOARDMODULEPATH = None
BOARDCALLBACK = None
BOARDCALLBACKPATH = None

def get_import_path():
    global IMPORTPATH

    if IMPORTPATH:
        return IMPORTPATH

    # check if we may have an old setup, so we are backward compatible
    IMPORTPATH = "tbotconfig"
    # check if there is a boardspecific.py file is found
    # if so, we have old setup. Drop a warning and use this
    # path
    if os.path.isfile(f"{IMPORTPATH}/boardspecific.py"):
        tbot.log.message(tbot.log.c("boardspecific.py found in tbotconfig, may you have an old setup").yellow)
        return IMPORTPATH

    # else search for boardspecific.py and labcallbacks.py in
    # path, where tbot.ini is found!
    for t in tbot.flags:
        if "inifile" in t:
            # inifile:tbotconfig/hs/tbot.ini
            # get import path!
            IMPORTPATH = t.split(":")[1]
            IMPORTPATH = os.path.dirname(IMPORTPATH).replace("/", ".")

    return IMPORTPATH

def get_boardmodulepath_import():
    global BOARDMODULEPATH

    if BOARDMODULEPATH:
        return BOARDMODULEPATH

    mp = get_import_path()
    BOARDMODULEPATH = f"{mp}.boardspecific"

    return BOARDMODULEPATH

def get_boardmodule_import():
    global BOARDMODULE
    if BOARDMODULE:
        return BOARDMODULE

    try:
        mp = get_boardmodulepath_import()
        BOARDMODULE = importlib.import_module(mp)

        return BOARDMODULE

    except Exception as e:
        raise RuntimeError(
            f"{e} Could not import module import path {importpath}.boardspecific"
        )

def get_boardcallbackpath_import():
    global BOARDCALLBACKPATH

    if BOARDCALLBACKPATH:
        return BOARDCALLBACKPATH

    mp = get_import_path()
    BOARDCALLBACKPATH = f"{mp}.labcallbacks"

    return BOARDCALLBACKPATH

def get_boardcallback_import():
    global BOARDCALLBACK
    if BOARDCALLBACK:
        return BOARDCALLBACK

    try:
        mp = get_boardcallbackpath_import()
        BOARDCALLBACK = importlib.import_module(mp)

        return BOARDCALLBACK

    except Exception as e:
        raise RuntimeError(
            f"{e} Could not import module import path {get_boardcallbackpath_import()}"
        )
