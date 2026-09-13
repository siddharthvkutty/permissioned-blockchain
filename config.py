"""
Shared network configuration.

These values must be IDENTICAL on the Mining Certificate Authority (MCA)
and on every node that joins the network, or blocks/certificates minted
on one machine will be rejected by another.

Every value can be overridden with an environment variable so you can
tune a network without editing code.
"""
import os

# Number of leading hex zeros a block hash must have to be accepted.
# Kept low on purpose so a normal desktop mines a block in a few seconds.
# 4 -> ~65k hashes on average, well under a second on modern hardware.
# 5 -> ~1M hashes on average, a few seconds. Raise/lower to taste.
DIFFICULTY = int(os.environ.get("CHAIN_DIFFICULTY", 5))

# Constant reward (in coins) paid to whoever successfully mines a block.
MINING_REWARD = float(os.environ.get("MINING_REWARD", 10))

# Coins every new account is granted at signup.
STARTING_BALANCE = float(os.environ.get("STARTING_BALANCE", 50))

# How long (in seconds) a mining certificate remains valid after issue.
# If a miner doesn't publish a block before this expires, or if the chain
# tip moves on before they finish, the certificate becomes useless and a
# fresh one must be requested.
CERT_VALIDITY_SECONDS = int(os.environ.get("CERT_VALIDITY_SECONDS", 300))

# Symbolic sender address used for coinbase-style entries: signup grants
# and mining rewards both appear to come "from" this address.
NETWORK_ADDRESS = "NETWORK"

# Separate admin credential used ONLY to manage the MCA's validator
# whitelist (who is allowed to mine at all). Should never be distributed
# to nodes - only the MCA reads it.
MCA_ADMIN_KEY = os.environ.get("MCA_ADMIN_KEY", "change-this-mca-admin-key")

# Default MCA location a fresh node will look for if MCA_URL isn't set.
DEFAULT_MCA_URL = os.environ.get("MCA_URL", "http://localhost:6060")
