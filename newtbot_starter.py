#!/usr/bin/python3

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
import re
import sys

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
sys.path.insert(0, currentdir + "/tbotconfig")
sys.path.insert(0, currentdir + "/../tbot")
sys.path.insert(0, currentdir + "/../tbottest")

from tbot.newbot import main  # noqa: E402

if __name__ == "__main__":
    sys.argv[0] = re.sub(r"(-script\.pyw?|\.exe)?$", "", sys.argv[0])
    args = sys.argv[1:]
    sys.exit(main(args))
