"""
Shared network configuration.

These values must be IDENTICAL on the MCA and on every node, or nodes
will compute different things (e.g. a different reward amount) than what
the rest of the network agrees on. Every value can be overridden with an
environment variable so you can tune a network without editing code.
"""
import os

# Constant reward (in coins) paid to whoever proposes an accepted block.
BLOCK_REWARD = float(os.environ.get("BLOCK_REWARD", 10))

# Coins every new account is granted at signup.
STARTING_BALANCE = float(os.environ.get("STARTING_BALANCE", 50))

# Symbolic sender address used for coinbase-style entries: signup grants
# and block-proposal rewards both appear to come "from" this address.
NETWORK_ADDRESS = "NETWORK"

# Admin credential used ONLY to manage the MCA's validator whitelist -
# who is allowed to propose blocks, and in what rotation order. Should
# never be distributed to node operators; only the MCA reads it.
MCA_ADMIN_KEY = os.environ.get("MCA_ADMIN_KEY", "quickbrownfox")

# How long (in seconds) a slot stays reserved for its primary validator
# before eligibility falls through to the next validator in rotation.
# This is what keeps the network from stalling forever if whoever's turn
# it is happens to be offline - see poa.py for the actual fallback math.
SLOT_TIMEOUT = float(os.environ.get("SLOT_TIMEOUT", 30))

# How far into the future a block's self-reported timestamp is allowed to
# be (to allow for reasonable clock drift between machines) before it's
# rejected outright. Without this, a dishonest proposer could claim a
# timestamp far enough ahead to unlock fallback eligibility instantly.
MAX_CLOCK_SKEW = float(os.environ.get("MAX_CLOCK_SKEW", 10))

# Default MCA location a fresh node will look for if MCA_URL isn't set.
DEFAULT_MCA_URL = os.environ.get("MCA_URL", "http://localhost:6060")
