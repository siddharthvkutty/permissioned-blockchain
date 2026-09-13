#!/usr/bin/env bash
# Starts a wallet/mining node.
# Usage: ./run_node.sh [port] [mca_url]
#   ./run_node.sh 5000 http://localhost:6060
#   ./run_node.sh 5001 http://192.168.1.10:6060
set -e
cd "$(dirname "$0")"
export PORT="${1:-5000}"
export MCA_URL="${2:-http://localhost:6060}"
python3 node_server.py
