#!/usr/bin/env bash
# Vendor three.js for the viewer. Kept OUT of git for the same reason as
# reference/: it is someone else's library, it is ~1.5 MB of minified-ish
# source, and pinning the version here is more honest than committing a copy
# nobody will ever read a diff of.
#
# The viewer must work with no network — a workshop room's wifi is not a
# dependency — hence vendoring rather than a CDN link.
set -euo pipefail
V=0.170.0
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
L="$HERE/viewer/lib"
mkdir -p "$L/jsm/controls" "$L/jsm/loaders" "$L/jsm/environments" "$L/jsm/utils"
base="https://unpkg.com/three@$V"
curl -sfL "$base/build/three.module.js"                        -o "$L/three.module.js"
curl -sfL "$base/examples/jsm/controls/OrbitControls.js"       -o "$L/jsm/controls/OrbitControls.js"
curl -sfL "$base/examples/jsm/loaders/GLTFLoader.js"           -o "$L/jsm/loaders/GLTFLoader.js"
curl -sfL "$base/examples/jsm/loaders/STLLoader.js"            -o "$L/jsm/loaders/STLLoader.js"
curl -sfL "$base/examples/jsm/environments/RoomEnvironment.js" -o "$L/jsm/environments/RoomEnvironment.js"
curl -sfL "$base/examples/jsm/utils/BufferGeometryUtils.js"    -o "$L/jsm/utils/BufferGeometryUtils.js"
echo "three.js $V -> viewer/lib ($(du -sh "$L" | cut -f1))"
