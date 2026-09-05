"""
Wallet cryptography helpers.

Every account gets a real ECDSA (secp256k1) keypair generated at signup.
Transactions are signed with the sender's private key and any peer can
verify authenticity with the sender's public key, exactly like a "real"
cryptocurrency wallet - the differences here are about scope, not the
signing scheme.

NOTE ON KEY CUSTODY: to keep the demo's UX simple (plain username/password
login, no seed phrases to manage), each node stores the private key
alongside the account record on that node's machine. This is a deliberate
simplification for a learning/demo project - see README.md's "Security
model & limitations" section before using this for anything real.
"""
import hashlib

from ecdsa import SigningKey, VerifyingKey, SECP256k1, BadSignatureError
from ecdsa.util import sigencode_der, sigdecode_der


def generate_keypair():
    """Returns (private_key_hex, public_key_hex)."""
    sk = SigningKey.generate(curve=SECP256k1)
    vk = sk.get_verifying_key()
    return sk.to_string().hex(), vk.to_string().hex()


def address_from_pubkey(pubkey_hex: str) -> str:
    """Derives a short wallet address from a public key, uniform with how
    most blockchains derive addresses (hash of the public key)."""
    return hashlib.sha256(bytes.fromhex(pubkey_hex)).hexdigest()[:40]


def sign(privkey_hex: str, message: str) -> str:
    sk = SigningKey.from_string(bytes.fromhex(privkey_hex), curve=SECP256k1)
    signature = sk.sign(message.encode("utf-8"), sigencode=sigencode_der)
    return signature.hex()


def verify(pubkey_hex: str, message: str, signature_hex: str) -> bool:
    try:
        vk = VerifyingKey.from_string(bytes.fromhex(pubkey_hex), curve=SECP256k1)
        return vk.verify(
            bytes.fromhex(signature_hex), message.encode("utf-8"), sigdecode=sigdecode_der
        )
    except (BadSignatureError, ValueError, TypeError):
        return False
