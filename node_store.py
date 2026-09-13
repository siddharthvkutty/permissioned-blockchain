"""
Persistent storage for a single node: accounts, the local chain, the
pending-transaction mempool, and known peers.

Storage is a single JSON file per node (keyed by port, so you can run
several nodes on one machine for testing). A threading.Lock guards writes.
This is intentionally simple (no external database) so the project has
zero setup beyond `pip install`.
"""
import json
import os
import threading
import time

from werkzeug.security import generate_password_hash, check_password_hash

import config


class NodeStore:
    def __init__(self, path: str):
        self.path = path
        self.lock = threading.Lock()
        self.data = {
            "accounts": {},     # address -> account dict
            "usernames": {},    # username (lowercase) -> address
            "chain": [],        # list of block dicts
            "mempool": [],      # list of pending transaction dicts
            "peers": [],        # list of peer base URLs, e.g. http://192.168.1.5:5000
            "balances": {},     # address -> float (cache, rebuilt from chain)
            "mca_pubkey": None,  # cached public key of the MCA this node talks to
        }
        self._load()

    # ---------------------------------------------------------- persistence
    def _load(self):
        if os.path.exists(self.path):
            with open(self.path, "r") as f:
                self.data = json.load(f)
        else:
            self._save()

    def _save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.data, f, indent=2)
        os.replace(tmp, self.path)

    # ---------------------------------------------------------------- accounts
    def create_account(self, username: str, password: str, address: str, pubkey: str, privkey: str):
        uname = username.strip().lower()
        with self.lock:
            if uname in self.data["usernames"]:
                return None
            account = {
                "address": address,
                "username": username.strip(),
                "password_hash": generate_password_hash(password),
                "pubkey": pubkey,
                "privkey": privkey,
                "genesis_balance": config.STARTING_BALANCE,
                "created_at": time.time(),
            }
            self.data["accounts"][address] = account
            self.data["usernames"][uname] = address
            self._recompute_balances_locked()
            self._save()
            return account

    def import_remote_account(self, account: dict) -> bool:
        """Used when another node on the network announces a brand-new
        signup, so every node has a consistent view of who exists."""
        with self.lock:
            addr = account["address"]
            uname = account["username"].strip().lower()
            if addr in self.data["accounts"] or uname in self.data["usernames"]:
                return False
            self.data["accounts"][addr] = account
            self.data["usernames"][uname] = addr
            self._recompute_balances_locked()
            self._save()
            return True

    def get_account_by_username(self, username: str):
        addr = self.data["usernames"].get(username.strip().lower())
        return self.data["accounts"].get(addr) if addr else None

    def get_account(self, address: str):
        return self.data["accounts"].get(address)

    def all_accounts(self):
        return list(self.data["accounts"].values())

    def verify_login(self, username: str, password: str):
        acc = self.get_account_by_username(username)
        if acc and check_password_hash(acc["password_hash"], password):
            return acc
        return None

    # ---------------------------------------------------------------- balances
    def _recompute_balances_locked(self):
        balances = {addr: acc["genesis_balance"] for addr, acc in self.data["accounts"].items()}
        for block in self.data["chain"]:
            for tx in block["transactions"]:
                sender, receiver, amount = tx["from"], tx["to"], tx["amount"]
                if sender != config.NETWORK_ADDRESS:
                    balances[sender] = balances.get(sender, 0.0) - amount
                balances[receiver] = balances.get(receiver, 0.0) + amount
        self.data["balances"] = balances

    def recompute_balances(self):
        with self.lock:
            self._recompute_balances_locked()
            self._save()

    def get_balance(self, address: str) -> float:
        return round(self.data["balances"].get(address, 0.0), 8)

    def get_pending_outgoing(self, address: str) -> float:
        return sum(t["amount"] for t in self.data["mempool"] if t["from"] == address)

    def get_spendable(self, address: str) -> float:
        return round(self.get_balance(address) - self.get_pending_outgoing(address), 8)

    # ---------------------------------------------------------------- mempool
    def add_to_mempool(self, tx: dict) -> bool:
        with self.lock:
            if any(t["tx_id"] == tx["tx_id"] for t in self.data["mempool"]):
                return False
            self.data["mempool"].append(tx)
            self._save()
            return True

    def get_mempool(self):
        return list(self.data["mempool"])

    def remove_from_mempool(self, tx_ids):
        tx_ids = set(tx_ids)
        with self.lock:
            self.data["mempool"] = [t for t in self.data["mempool"] if t["tx_id"] not in tx_ids]
            self._save()

    # ---------------------------------------------------------------- chain
    def get_chain(self):
        return list(self.data["chain"])

    def get_tip(self):
        chain = self.data["chain"]
        return chain[-1] if chain else None

    def append_block(self, block_dict: dict, included_tx_ids):
        included_tx_ids = set(included_tx_ids)
        with self.lock:
            self.data["chain"].append(block_dict)
            self.data["mempool"] = [t for t in self.data["mempool"] if t["tx_id"] not in included_tx_ids]
            self._recompute_balances_locked()
            self._save()

    def replace_chain(self, new_chain: list):
        with self.lock:
            self.data["chain"] = new_chain
            included = set()
            for b in new_chain:
                for tx in b["transactions"]:
                    included.add(tx["tx_id"])
            self.data["mempool"] = [t for t in self.data["mempool"] if t["tx_id"] not in included]
            self._recompute_balances_locked()
            self._save()

    # ---------------------------------------------------------------- peers
    def add_peer(self, url: str):
        url = url.rstrip("/")
        with self.lock:
            if url not in self.data["peers"]:
                self.data["peers"].append(url)
                self._save()

    def get_peers(self):
        return list(self.data["peers"])

    # ---------------------------------------------------------------- MCA identity
    def get_cached_mca_pubkey(self):
        return self.data.get("mca_pubkey")

    def set_cached_mca_pubkey(self, pubkey: str):
        with self.lock:
            self.data["mca_pubkey"] = pubkey
            self._save()
