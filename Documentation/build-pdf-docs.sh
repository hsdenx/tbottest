#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

echo build with "export PYTHONPATH=<path to tbot>"

sphinx-build -b latex -t pygments-light . ./output-pdf
make -C ./output-pdf
