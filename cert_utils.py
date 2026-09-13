"""
Pure certificate signing/verification logic, shared by the MCA (which
issues and administers certificates) and every node (which only ever
needs to *verify* a certificate's authenticity - never issue, store, or
administer one).

Certificates are signed with the MCA's own ECDSA private key, generated
once and never leaving the MCA's machine. Every node verifies signatures
with the MCA's PUBLIC key instead - which, unlike a shared secret, is
completely safe to print, publish, or hand to every node in the network.
This replaces an earlier design that used one symmetric HMAC secret
copy-pasted onto every machine, where a single leaked node was enough to
let an attacker forge certificates for the whole network.

This file contains no storage and no admin capability - just the ECDSA
math (delegated to crypto_utils, the same module wallets use) - so a
node-only distribution can include it without pulling in any MCA
administration code.
"""
import json

import crypto_utils

CERT_FIELDS = ("cert_id", "miner_address", "block_index", "prev_hash", "issued_at", "expires_at")


def _canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True)


def sign_payload(payload: dict, mca_privkey_hex: str) -> str:
    """Only ever called on the MCA - it's the only place the private key exists."""
    return crypto_utils.sign(mca_privkey_hex, _canonical(payload))


def verify_signature(payload: dict, signature: str, mca_pubkey_hex: str) -> bool:
    """Safe to call anywhere - only needs the MCA's PUBLIC key, never the private one."""
    if not signature or not mca_pubkey_hex:
        return False
    return crypto_utils.verify(mca_pubkey_hex, _canonical(payload), signature)
