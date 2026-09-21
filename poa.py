"""
Proof-of-Authority (PoA) consensus helpers.

Block production rotates deterministically among the MCA's approved
validators, in the order they were approved. Whoever's turn it is signs
the block with their own wallet key; everyone else verifies that
signature and confirms the proposer was genuinely eligible before
accepting the block.

LIVENESS FALLBACK: a pure "block_index % len(validators)" rotation has a
real problem - if whoever's turn it is happens to be offline, the
network stalls forever, since nobody else is "allowed" to propose. This
module fixes that with a timeout: a slot belongs to its PRIMARY validator
for SLOT_TIMEOUT seconds after the previous block was produced; if
nothing shows up in that window, eligibility falls through to the next
validator in rotation, then the next, and so on, cycling indefinitely
until someone actually proposes. Because eligibility is computed purely
from (validator list, block index, previous block's timestamp, current
time), every node reaches the same answer independently - no separate
coordination round is needed to agree on "whose turn is it NOW".
"""
import crypto_utils


def primary_proposer(validators: list, block_index: int):
    """The validator originally scheduled for this slot, ignoring
    timeouts - useful for display ("who's supposed to go") even once
    eligibility has fallen through to someone else."""
    if not validators:
        return None
    return validators[block_index % len(validators)]


def eligible_proposer(validators: list, block_index: int, prev_timestamp: float,
                       now: float, slot_timeout: float):
    """Who may ACTUALLY propose this block right now. Matches
    primary_proposer() for the first `slot_timeout` seconds after the
    previous block; after that, eligibility shifts to the next validator
    in rotation for each additional `slot_timeout` window that elapses,
    wrapping around indefinitely. Returns None if there are no
    validators at all.

    NOTE on the network's very first block: genesis carries a fixed,
    non-real timestamp (0.0) so its hash is identical across fresh nodes
    (see blockchain.py) - real elapsed time since "genesis" is therefore
    a huge, epoch-anchored number rather than anything meaningful in
    human terms. This is harmless to correctness (the formula is still
    fully deterministic and reproducible by every verifier - it just
    means the specific validator who gets first dibs on block 1 may not
    line up with position 0, though the modulo below still keeps any
    displayed countdown in a normal, sane range). From the second real
    block onward, every timestamp involved is genuine wall-clock time
    and this quirk no longer applies.
    """
    if not validators:
        return None
    elapsed = max(0.0, now - prev_timestamp)
    skips = int(elapsed // slot_timeout) if slot_timeout > 0 else 0
    position = (block_index + skips) % len(validators)
    return validators[position]


def seconds_until_fallback(prev_timestamp: float, now: float, slot_timeout: float) -> float:
    """How many seconds remain before eligibility shifts to the next
    validator in rotation - purely for display on the Validator page.
    The modulo keeps this in a normal, human-sized range even right
    after genesis, despite genesis's epoch-anchored timestamp (see
    eligible_proposer's docstring)."""
    if slot_timeout <= 0:
        return 0.0
    elapsed = max(0.0, now - prev_timestamp)
    remaining = slot_timeout - (elapsed % slot_timeout)
    return round(remaining, 1)


def sign_block(privkey_hex: str, block_hash: str) -> str:
    """Only ever called by the validator proposing the block."""
    return crypto_utils.sign(privkey_hex, block_hash)


def verify_block_signature(pubkey_hex: str, block_hash: str, signature: str) -> bool:
    """Safe to call anywhere - only needs the proposer's public key,
    which every node already has from ordinary account replication."""
    if not signature or not pubkey_hex:
        return False
    return crypto_utils.verify(pubkey_hex, block_hash, signature)
