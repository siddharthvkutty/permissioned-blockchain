"""
Storage and signing logic for the Mining Certificate Authority (MCA).

A certificate is a permission slip for mining exactly one specific block:
it is bound to a miner's address, the exact index the block must occupy,
and the exact previous-hash it must build on. It is single-use and time
limited. This is what makes the chain "permissioned": nobody can publish
a block, however good their proof-of-work is, without first obtaining and
including a valid certificate that the MCA has on record.
"""
import hashlib
import hmac
import json
import os
import threading
import time

import config


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True).encode("utf-8")


def sign_payload(payload: dict) -> str:
    return hmac.new(config.MCA_SECRET_KEY.encode("utf-8"), _canonical(payload), hashlib.sha256).hexdigest()


def verify_signature(payload: dict, signature: str) -> bool:
    expected = sign_payload(payload)
    try:
        return hmac.compare_digest(expected, signature)
    except TypeError:
        return False


CERT_FIELDS = ("cert_id", "miner_address", "block_index", "prev_hash", "issued_at", "expires_at")


class MCAStore:
    def __init__(self, path: str):
        self.path = path
        self.lock = threading.Lock()
        self.data = {"certificates": {}}
        self._load()

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
            cert["signature"] = sign_payload(payload)
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
        if not verify_signature(payload, record["signature"]):
            return False, "signature mismatch", record

        if record["expires_at"] < time.time():
            return False, "certificate expired", record

        if (submitted_cert.get("block_index") != record["block_index"]
                or submitted_cert.get("prev_hash") != record["prev_hash"]
                or submitted_cert.get("miner_address") != record["miner_address"]):
            return False, "certificate does not match this block", record

        if record["used"]:
            return False, "certificate already used", record

        if mark_used:
            with self.lock:
                if record["used"]:
                    return False, "certificate already used", record
                record["used"] = True
                self._save()

        return True, "ok", record
