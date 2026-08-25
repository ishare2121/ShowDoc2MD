#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
echo
echo "安装完成。"
echo "用法：source .venv/bin/activate && showdoc2md export '<SHOWDOC_URL>' --password '<PASSWORD>'"
