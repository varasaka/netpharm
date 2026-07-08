#!/usr/bin/env bash
# ============================================================
#  Build the macOS desktop app. Run this ON macOS.
#  Requires: Python 3.10-3.12.
# ============================================================
set -e
echo "[1/4] Creating build environment..."
python3 -m venv .build-venv
source .build-venv/bin/activate

echo "[2/4] Installing dependencies (several minutes)..."
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

echo "[3/4] Freezing the app..."
pyinstaller packaging/netpharm.spec --noconfirm

echo "[4/4] Done."
echo "  App folder:  dist/NetworkPharmacology/"
echo "  Run it:      ./dist/NetworkPharmacology/NetworkPharmacology"
echo "  Optional (ADME/target agents), one time:  playwright install chromium"
