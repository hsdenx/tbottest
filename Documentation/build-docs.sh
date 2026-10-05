#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

echo build with "export PYTHONPATH=<path to tbot>"

if [ "$1" = "--all-themes" ]; then
    shift
    # sphinx_rtd_theme into output/, every other theme of DOC_THEMES in
    # conf.py into output/<theme>/, each page with a menu to switch
    export TBOTTEST_DOC_THEMESWITCH=1
    for theme in rtd piccolo cloud nefertiti; do
        out=./output
        if [ "$theme" != "rtd" ]; then
            out=./output/$theme
        fi
        TBOTTEST_DOC_THEME=$theme sphinx-build -b html . "$out"
    done
else
    sphinx-build -b html . ./output
fi

if [ "$1" = "--open" ]; then
   xdg-open ./output/index.html
fi
