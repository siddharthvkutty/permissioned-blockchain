"""
Storage for the Mining Certificate Authority (MCA) - which, under PoA,
is really just a validator REGISTRY: the one authoritative, centrally
administered list of which wallet addresses are allowed to propose
blocks, and in what order they take turns.

Unlike the network's earlier design, the MCA no longer signs, issues, or
stores anything about individual blocks - it never even sees a block.
Its only job is admitting/removing validators and publishing the current
list, which is what makes rotation-based consensus (see poa.py) possible
without a live round-trip to the MCA for every single block.

Validators are stored in a plain dict; Python dicts preserve insertion
order, so the order addresses were approved IS the rotation order -
first approved goes first, and so on.
"""
import json
import os
import threading
import time


class MCAStore:
    def __init__(self, path: str):
        self.path = path
        self.lock = threading.Lock()
        self.data = {"validators": {}}
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            with open(self.path, "r") as f:
                self.data = json.load(f)
        else:
            self._save()
        self.data.setdefault("validators", {})

    def _save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.data, f, indent=2)
        os.replace(tmp, self.path)

    # ------------------------------------------------------- validator admission
    def add_validator(self, address: str, label: str = "") -> None:
        """If the address is already a validator, this does NOT move it in
        the rotation order (re-approving isn't the same as re-joining) -
        it just updates the label."""
        with self.lock:
            existing = self.data["validators"].get(address)
            added_at = existing["added_at"] if existing else time.time()
            self.data["validators"][address] = {"label": label, "added_at": added_at}
            self._save()

    def remove_validator(self, address: str) -> bool:
        with self.lock:
            existed = self.data["validators"].pop(address, None) is not None
            if existed:
                self._save()
            return existed

    def is_validator(self, address: str) -> bool:
        return address in self.data["validators"]

    def list_validators(self) -> dict:
        """Ordered by approval order (insertion order)."""
        return dict(self.data["validators"])

    def ordered_addresses(self) -> list:
        """Just the addresses, in rotation order - what nodes actually
        need to compute whose turn it is."""
        return list(self.data["validators"].keys())
