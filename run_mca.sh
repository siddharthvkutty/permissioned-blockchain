#!/usr/bin/env bash
# Starts the validator registry (MCA).
# Usage: ./run_mca.sh [port]
set -e
cd "$(dirname "$0")"
export MCA_PORT="${1:-6060}"
python3 mca_server.py
