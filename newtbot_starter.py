#!/usr/bin/env python3

# -*- coding: utf-8 -*-

"""
TBot files may be install in the OS by running setup.py inside the git repository.
To run TBot without installing the files you may run this script.

add commandline completion

add current workdir to path:

    export PATH=$(pwd):${PATH}

source tbots completions script:

    source ../tbot/completions.sh

add newtbot_starter.py

    complete -F _newbot newtbot_starter.py

"""

import inspect
import os
import sys
import time

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
try:
    TBOTCONFIGPATH = os.environ['TBOTCONFIGPATH']
    sys.path.insert(0, TBOTCONFIGPATH)
except:
    sys.path.insert(0, currentdir + "/tbotconfig")

sys.path.insert(0, currentdir + "/../tbot")
try:
    TBOTTESTPATH = os.environ['TBOTTESTPATH']
    sys.path.insert(0, TBOTTESTPATH)
except:
    sys.path.insert(0, currentdir + "/../tbottest")

from tbot.newbot import main  # noqa: E402

if __name__ == "__main__":
    # start time of this run for argumentfiles, which tbot expands shell
    # variables in, e.g. "--json-log-stream" "log/${TBOT_STARTTIME}.log"
    os.environ.setdefault("TBOT_STARTTIME", time.strftime("%Y%m%d-%H%M%S"))
    args = sys.argv[1:]
    sys.argv = args
    sys.exit(main(args))
