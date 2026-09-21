"""
Core block data structure.

Blocks are no longer "mined" - there is no puzzle and no nonce. A block
is valid because it was produced, in turn, by an approved validator, and
signed with that validator's own wallet key (see poa.py). This module
only defines the block's shape and its hash; the consensus rules that
decide whether a given block SHOULD be accepted live in poa.py and in
each node's validation logic.
"""
import hashlib
import json

GENESIS_PREV_HASH = "0" * 64


class Block:
    def __init__(self, index, timestamp, transactions, previous_hash,
                 proposer=None, signature=None, hash_=None):
        self.index = index
        self.timestamp = timestamp
        self.transactions = transactions          # list of tx dicts
        self.previous_hash = previous_hash
        self.proposer = proposer                   # validator address that produced this block
        self.signature = signature                 # proposer's ECDSA signature over this block's hash
        self.hash = hash_ or self.compute_hash()

    def header_string(self) -> str:
        payload = {
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "previous_hash": self.previous_hash,
            "proposer": self.proposer,
        }
        return json.dumps(payload, sort_keys=True)

    def compute_hash(self) -> str:
        return hashlib.sha256(self.header_string().encode("utf-8")).hexdigest()

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "previous_hash": self.previous_hash,
            "proposer": self.proposer,
            "signature": self.signature,
            "hash": self.hash,
        }

    @staticmethod
    def from_dict(d: dict) -> "Block":
        return Block(
            index=d["index"],
            timestamp=d["timestamp"],
            transactions=d["transactions"],
            previous_hash=d["previous_hash"],
            proposer=d.get("proposer"),
            signature=d.get("signature"),
            hash_=d["hash"],
        )


def make_genesis_block() -> Block:
    """Identical on every fresh node - fixed timestamp/content so genesis
    hashes match across machines that have never synced with each other."""
    return Block(0, 0.0, [], GENESIS_PREV_HASH, proposer=None, signature=None)
