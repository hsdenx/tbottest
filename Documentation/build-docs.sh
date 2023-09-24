#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

echo build with "export PYTHONPATH=<path to tbot>"

sphinx-build -b html . ./output

if [ "$1" = "--open" ]; then
   xdg-open ./output/index.html
fi
