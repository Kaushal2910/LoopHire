#!/bin/bash
echo "Starting setup..."
if command -v python3 &>/dev/null; then
    python3 setup.py
elif command -v python &>/dev/null; then
    python setup.py
else
    echo "[ERROR] Python 3 is required but was not found on your system."
    echo "Please install Python 3 and try again."
    exit 1
fi
