#!/bin/zsh
cd -- "${0:A:h}" || exit 1
if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv || exit 1
  .venv/bin/python -m pip install -r requirements.txt || exit 1
fi
printf 'Camera number (0, 1 or 2; press Enter for 0): '
read camera_number
.venv/bin/python camera_control.py --camera "${camera_number:-0}"
printf '\nPress Enter to close. '
read
