#!/bin/bash
cd ~/msn-museum
source venv/bin/activate
export PYTHONPATH=.
exec python3 -u run_all.py
