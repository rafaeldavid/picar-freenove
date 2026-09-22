#!/usr/bin/env bash
# Build the Python env the CAD work needs. OpenCASCADE via cadquery-ocp is the
# only thing on this machine that reads STEP; scipy is for the fit tests.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 -m venv "$HERE/cadenv"
"$HERE/cadenv/bin/pip" install -q --upgrade pip
"$HERE/cadenv/bin/pip" install cadquery scipy numpy
"$HERE/cadenv/bin/python" -c "import cadquery, scipy, numpy; print('cad env ready')"
