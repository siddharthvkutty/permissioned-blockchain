"""
Storage and issuance/administration logic for the Mining Certificate
Authority (MCA).

A certificate is a permission slip for mining exactly one specific block:
it is bound to a miner's address, the exact index the block must occupy,
and the exact previous-hash it must build on. It is single-use and time
limited. This is what makes the chain "permissioned": nobody can publish
a block, however good their proof-of-work is, without first obtaining and
including a valid certificate that the MCA has on record - and, on top
of that, only addresses the MCA's administrator has approved as
validators can obtain one at all.

The pure signing/verification math lives in cert_utils.py (shared with
nodes); everything in THIS file - issuance, the validator whitelist,
administration - is MCA-only and never needed by a node.
"""
import hashlib
import json
import os
import threading
import time

import config
import crypto_utils
from cert_utils import CERT_FIELDS, sign_payload, verify_signature


class MCAStore:
    def __init__(self, path: str):
        self.path = path
        self.lock = threading.Lock()
        self.data = {"certificates": {}, "validators": {}}
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            with open(self.path, "r") as f:
                self.data = json.load(f)
        else:
            self._save()
        # Files created before certain features existed won't have these
        # keys yet - backfill so older data files still load correctly.
        self.data.setdefault("validators", {})
        if "identity" not in self.data:
            # This MCA's own signing keypair. Generated once and persisted
            # so restarts keep the same identity (and keep every
            # certificate anyone still holds - and every node's cached
            # copy of this public key - valid) rather than silently
            # becoming a "different" MCA on every restart.
            privkey, pubkey = crypto_utils.generate_keypair()
            self.data["identity"] = {"privkey": privkey, "pubkey": pubkey}
            self._save()

    def get_public_key(self) -> str:
        """Safe to hand out to anyone - nodes need this to verify certificates."""
        return self.data["identity"]["pubkey"]

    def _private_key(self) -> str:
        """NEVER exposed over the network - only used internally to sign."""
        return self.data["identity"]["privkey"]

    def _save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.data, f, indent=2)
        os.replace(tmp, self.path)

    # ------------------------------------------------------- validator admission
    # Being a member of the network (an account on some node) and being
    # AUTHORIZED TO MINE are deliberately two separate things. This
    # whitelist is what an operator uses to decide the latter, and it is
    # kept ONLY here on the MCA - never inside a node's replicated account
    # data - specifically so that no node operator can grant themselves
    # mining rights by editing their own local files. See README for the
    # full reasoning.
    def add_validator(self, address: str, label: str = "") -> None:
        with self.lock:
            self.data["validators"][address] = {"label": label, "added_at": time.time()}
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
        return dict(self.data["validators"])

    # ------------------------------------------------------------ certificates
    def issue_certificate(self, miner_address: str, block_index: int, prev_hash: str) -> dict:
        with self.lock:
            issued_at = time.time()
            seed = f"{miner_address}{block_index}{prev_hash}{issued_at}{os.urandom(8).hex()}"
            cert_id = hashlib.sha256(seed.encode("utf-8")).hexdigest()
            payload = {
                "cert_id": cert_id,
                "miner_address": miner_address,
                "block_index": block_index,
                "prev_hash": prev_hash,
                "issued_at": issued_at,
                "expires_at": issued_at + config.CERT_VALIDITY_SECONDS,
            }
            cert = dict(payload)
            cert["signature"] = sign_payload(payload, self._private_key())
            cert["used"] = False
            self.data["certificates"][cert_id] = cert
            self._save()
            return cert

    def get(self, cert_id: str):
        return self.data["certificates"].get(cert_id)

    def mark_used(self, cert_id: str) -> bool:
        with self.lock:
            cert = self.data["certificates"].get(cert_id)
            if cert and not cert["used"]:
                cert["used"] = True
                self._save()
                return True
            return False

    def all_certificates(self):
        return sorted(self.data["certificates"].values(), key=lambda c: c["issued_at"], reverse=True)

    def evaluate(self, submitted_cert: dict, mark_used: bool):
        """Runs the full authenticity check for a certificate a node is
        trying to redeem, and optionally consumes it. Returns (valid, reason, record)."""
        cert_id = submitted_cert.get("cert_id")
        record = self.get(cert_id)
        if not record:
            return False, "unknown certificate", None

        payload = {k: record[k] for k in CERT_FIELDS}
        if not verify_signature(payload, record["signature"], self.get_public_key()):
            return False, "signature mismatch", record

        if record["expires_at"] < time.time():
            return False, "certificate expired", record

        if (submitted_cert.get("block_index") != record["block_index"]
                or submitted_cert.get("prev_hash") != record["prev_hash"]
                or submitted_cert.get("miner_address") != record["miner_address"]):
            return False, "certificate does not match this block", record

        if record["used"]:
            return False, "certificate already used", record

        # Defense in depth: even though issuance already checked this, an
        # admin may have revoked this address between issuance and
        # redemption (e.g. mid-mining). Re-check right before a block is
        # actually accepted.
        if not self.is_validator(record["miner_address"]):
            return False, "miner is no longer an authorized validator", record

        if mark_used:
            with self.lock:
                if record["used"]:
                    return False, "certificate already used", record
                record["used"] = True
                self._save()

        return True, "ok", record
