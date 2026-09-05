"""
Core block data structure and the (deliberately light) proof-of-work.
"""
import hashlib
import json

GENESIS_PREV_HASH = "0" * 64


class Block:
    def __init__(self, index, timestamp, transactions, previous_hash,
                 certificate=None, nonce=0, miner=None, hash_=None):
        self.index = index
        self.timestamp = timestamp
        self.transactions = transactions          # list of tx dicts
        self.previous_hash = previous_hash
        self.certificate = certificate             # dict issued by the MCA, or None for genesis
        self.nonce = nonce
        self.miner = miner                          # address of the miner, or None for genesis
        self.hash = hash_ or self.compute_hash()

    def header_string(self) -> str:
        """Canonical representation that gets hashed. Only the certificate's
        id is included (not the whole cert) so the header stays compact;
        the certificate's authenticity is checked separately."""
        payload = {
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "previous_hash": self.previous_hash,
            "certificate_id": (self.certificate or {}).get("cert_id"),
            "miner": self.miner,
            "nonce": self.nonce,
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
            "certificate": self.certificate,
            "nonce": self.nonce,
            "miner": self.miner,
            "hash": self.hash,
        }

    @staticmethod
    def from_dict(d: dict) -> "Block":
        return Block(
            index=d["index"],
            timestamp=d["timestamp"],
            transactions=d["transactions"],
            previous_hash=d["previous_hash"],
            certificate=d.get("certificate"),
            nonce=d["nonce"],
            miner=d.get("miner"),
            hash_=d["hash"],
        )


def make_genesis_block() -> Block:
    """The genesis block must be byte-for-byte identical on every node that
    ever joins the network, or chains can never link up between machines.
    So this uses a fixed timestamp/nonce rather than `time.time()` -
    every fresh node produces the exact same genesis hash."""
    return Block(0, 0.0, [], GENESIS_PREV_HASH, certificate=None, nonce=0, miner=None)


def meets_difficulty(hash_hex: str, difficulty: int) -> bool:
    return hash_hex.startswith("0" * difficulty)


def mine_block(block: Block, difficulty: int, stop_check=None):
    """Increments the nonce until the block's hash has `difficulty` leading
    hex zeros. This is intentionally light so a normal desktop finishes in
    at most a few seconds.

    `stop_check` is an optional zero-arg callable; if it ever returns True,
    mining aborts early and this returns None (used so a miner can bail out
    the moment the chain tip moves on and its certificate becomes stale).
    """
    block.nonce = 0
    block.hash = block.compute_hash()
    while not meets_difficulty(block.hash, difficulty):
        if stop_check is not None and stop_check():
            return None
        block.nonce += 1
        block.hash = block.compute_hash()
    return block
