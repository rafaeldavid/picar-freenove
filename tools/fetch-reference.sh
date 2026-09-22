#!/usr/bin/env bash
# Repopulate reference/ — Freenove's own code and docs, kept OUT of git.
#
# Why not vendor it: it is Freenove's, the tutorials are CC BY-NC-SA, and a full
# clone of their repo is ~195 MB of PDFs. We keep a sparse copy for reading and
# for the LED probe, which borrows their two WS2812 encoders.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$HERE/reference"
LOCAL="$HOME/Documents/protocolized-publications/_local-downloads/Freenove_4WD_Smart_Car_Kit_for_Raspberry_Pi-master 2"
REPO="https://github.com/Freenove/Freenove_4WD_Smart_Car_Kit_for_Raspberry_Pi.git"

mkdir -p "$DEST/docs" "$DEST/freenove-upstream"

if [ -d "$LOCAL" ]; then
  echo "using the local copy at $LOCAL"
  rsync -a --exclude='__pycache__' "$LOCAL/Code/" "$DEST/freenove-upstream/Code/"
  cp "$LOCAL/LICENSE.txt" "$DEST/freenove-upstream/"
  cp "$LOCAL/Picture/PCB_V"*.png "$DEST/docs/"
  cp "$LOCAL/Datasheet/ADS7830.pdf" "$LOCAL/Datasheet/PCA9685.pdf" "$DEST/docs/"
  if command -v pdftotext >/dev/null; then
    pdftotext -layout "$LOCAL/Tutorial(mecanum_wheels).pdf" "$DEST/docs/tutorial-mecanum.txt"
    pdftotext -layout "$LOCAL/About_Battery.pdf"            "$DEST/docs/about-battery.txt"
  fi
else
  echo "local copy not found; sparse-cloning from GitHub"
  tmp="$(mktemp -d)"
  git clone --depth 1 --filter=blob:none --sparse "$REPO" "$tmp/kit"
  git -C "$tmp/kit" sparse-checkout set Code Picture Datasheet
  rsync -a --exclude='__pycache__' "$tmp/kit/Code/" "$DEST/freenove-upstream/Code/"
  cp "$tmp/kit/Picture/PCB_V"*.png "$DEST/docs/" 2>/dev/null || true
  cp "$tmp/kit/Datasheet/"*.pdf     "$DEST/docs/" 2>/dev/null || true
  rm -rf "$tmp"
fi

echo "reference/ is $(du -sh "$DEST" | cut -f1)"
