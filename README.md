# Permissioned Chain (Proof-of-Authority)

A small, self-contained **permissioned blockchain network** with a real web
GUI, built with Python and Flask. It works on Linux and Windows (anywhere
Python 3 runs) and is designed to be run across multiple machines on the
same LAN.

- **Permissioned**: nobody can see or use the chain without an account.
- **Wallets for everyone**: sign up and you're instantly granted 50 coins.
- **Ordinary transactions**: send coins to any other user on the network.
- **Proof-of-Authority consensus**: block production rotates
  deterministically among a small set of pre-approved validators - no
  mining, no puzzle to solve, no race. Exactly one validator is eligible
  per block, in a fixed order, and everyone else simply verifies their
  signature.
- **Constant block-proposal reward**: every accepted block pays the same
  reward to whoever proposed it.

> **A note for anyone comparing this to an earlier version of this
> project:** an earlier iteration used competitive proof-of-work mining
> gated by single-use certificates from a Mining Certificate Authority.
> That version is preserved on a separate branch. This version replaces
> that whole mechanism with Proof-of-Authority, described below - the
> reasoning is that in a network where every participant's identity is
> already vetted (which is the entire point of "permissioned"), racing to
> solve a computational puzzle to prove you're not a stranger is solving
> a problem the network doesn't actually have. See "Why PoA instead of
> PoW here" below for the full reasoning.

---

## How it fits together

There are two kinds of service in this project:

```
                     ┌─────────────────────────┐
                     │  Validator Registry       │
                     │  ("MCA") - mca_server.py  │   <- one per network,
                     │  who may propose, in what │      must stay running
                     │  order                    │
                     └───────────┬──────────────┘
                                 │  GET /validators (public, read-only)
                 ┌───────────────┼────────────────┐
                 │               │                │
        ┌────────▼───────┐ ┌─────▼──────────┐ ┌───▼────────────┐
        │ Node (machine A)│ │ Node (machine B)│ │ Node (machine C)│
        │ node_server.py  │ │ node_server.py  │ │ node_server.py  │
        │ Wallet + Validator interface, web GUI, peer-to-peer sync │
        └─────────────────┘ └─────────────────┘ └─────────────────┘
```

- **`mca_server.py`** — the validator registry. Despite the historical
  name (MCA = Mining Certificate Authority, from the project's earlier
  PoW design), it no longer issues certificates or touches blocks at
  all. Its entire job is being the one authoritative, admin-managed list
  of which wallet addresses may propose blocks, and in what order. Run
  exactly one per network; it has no login, it's an internal service
  other machines read from over plain HTTP.
- **`node_server.py`** — the program each person on the network actually
  uses. It serves the wallet dashboard and the validator interface as a
  normal web page. Run one instance per machine/person. Nodes register
  with each other as **peers** and gossip accounts, transactions, and
  blocks over plain REST endpoints so everyone converges on the same
  ledger — nothing about the transport layer changed from the project's
  earlier design, only what happens at "produce a block."

See **[USAGE.md](USAGE.md)** for exact step-by-step commands, including
multi-machine setup.

---

## How consensus works: Proof-of-Authority

1. A network administrator approves specific wallet addresses as
   **validators** on the registry's `/admin/validators` page (protected
   by a separate admin key, `MCA_ADMIN_KEY`, never distributed to nodes).
   The order they're approved in **is** the rotation order.
2. For any given block index, exactly one validator is eligible:
   `validators[block_index % len(validators)]`. Every node can compute
   this itself — it only needs the (public) ordered validator list,
   fetched from the registry's `GET /validators`.
3. When it's their turn, that validator's node assembles pending
   transactions, builds the block, and **signs it with their own wallet's
   private key** — the very same ECDSA key used to sign transactions.
   There's no separate mining identity or certificate to manage.
4. The block is appended locally and broadcast to peers. Every peer that
   receives it independently checks: does the hash match the content, is
   the named proposer actually the address that was eligible *at the
   moment they claim to have proposed* (see the liveness fallback
   below), and does the signature genuinely verify against that
   proposer's known public key (already known from ordinary account
   replication)? Only then is the block accepted.

Because a block is only valid coming from one specific, known address at
a time, there's nothing to race for and nothing to solve — a node either
has the right to propose right now, or it doesn't, and every other node
can check that fact for itself using only public information.

### Liveness: what happens if whoever's turn it is goes offline

A pure `block_index % len(validators)` rotation has a real problem: if
the validator whose turn it is happens to be offline, nobody else is
"allowed" to propose, and the network stalls forever waiting for someone
who isn't coming back. This is solved with a timeout (`SLOT_TIMEOUT` in
`config.py`, default 30s): a slot belongs to its **primary** validator
for that many seconds after the previous block was produced. If nothing
arrives in that window, eligibility automatically shifts to the next
validator in rotation, then the next, cycling indefinitely until someone
actually proposes.

The elegant part: eligibility is a **pure function** of (validator list,
block index, previous block's timestamp, current time) — every node
computes the same answer completely independently, with no extra
coordination round needed to agree on "whose turn is it *now*." When
verifying a block someone else proposed, nodes use that block's own
claimed timestamp (bounded by a small allowed clock-skew window) rather
than their own local clock, so ordinary network propagation delay never
causes an honestly-produced block to be wrongly rejected.

The Validator page shows this directly: whether it's currently your
turn, whether that's because you're the scheduled primary or because
fallback has kicked in, and a live countdown to when eligibility will
next shift if nobody acts.

### Why PoA instead of PoW here

Proof-of-Work exists to solve a specific problem: letting mutually
distrusting strangers with no shared identity agree on a single history,
by making it expensive to attempt to cheat and cheap to verify. A
permissioned network has already solved a *different* version of that
problem — identity is vetted up front, via the validator whitelist —
before a single block is ever produced. Spending CPU cycles racing
already-known, already-trusted participants against each other doesn't
add anything a permissioned network doesn't already have; it just adds
latency and wasted computation. This is exactly why real permissioned/
consortium chains (Hyperledger Fabric's ordering service, Ethereum's
Clique and Aura PoA clients, etc.) use authority-based rotation instead
of competitive mining once membership is already controlled.

### A known, honestly-flagged limitation

Validator set changes (an admin approving or revoking someone) aren't
recorded *on the chain itself* — they only live in the registry's own
data. This means that when a node does a full historical chain resync
from a peer, it validates each historical block's proposer against the
**current** validator set, not the set that was actually in effect at
the time that specific block was produced. For blocks as they're freshly
produced (the common case, handled in `/p2p/blocks`), this is fully
correct — "current" and "historical" are the same thing at that instant.
The gap only matters if you resync a long history after the validator
set has since changed. A more rigorous version of this project would
record validator admissions/revocations as special transactions inside
the chain itself, so historical blocks could always be checked against
the set that was genuinely in effect when they were made — a natural
next step, not implemented here.

---

## Feature checklist against the original brief

- [x] Permissioned network — sign-up/login required to see or use the chain.
- [x] Every account starts with 50 coins.
- [x] Ordinary peer-to-peer transactions between users.
- [x] A separate "Validator" interface, reached by a button redirect from
      the wallet dashboard.
- [x] A centrally-administered validator registry that must be running
      for anyone to know whose turn it is to propose.
- [x] Deterministic, race-free block production — exactly one eligible
      proposer per block, verifiable by anyone from public information.
- [x] Automatic liveness fallback — an offline validator's slot times out
      and shifts to the next validator, so a single unavailable
      participant can't stall the network.
- [x] Constant block-proposal rewards.
- [x] A proper (browser-based) GUI that runs the same way on Linux and
      Windows.

---

## Project layout

```
permissioned-blockchain/
├── config.py          shared network parameters (block reward, admin key...)
├── crypto_utils.py     ECDSA keypair generation / signing / verification (wallets AND block signing)
├── blockchain.py       Block structure (proposer + signature, no PoW/nonce)
├── poa.py              pure PoA consensus math: rotation + block signing helpers
├── mca_store.py        validator whitelist storage (the registry's only job)
├── mca_server.py         <- run this to start the validator registry
├── node_store.py       account/chain/mempool/peer/validator-cache storage for a node
├── node_server.py       <- run this to start a wallet + validator node
├── templates/          Jinja2 HTML templates for the web GUI
├── static/              CSS + JS for the web GUI
├── run_mca.sh / .bat    convenience launchers for the registry
├── run_node.sh / .bat   convenience launchers for a node
├── requirements.txt
└── USAGE.md             step-by-step instructions
```

---

## Security model & limitations (read this before using it for anything real)

This project is a teaching/demo network, not production financial
infrastructure. Specifically, by design:

- **Custodial-style key storage.** Signing up generates a real ECDSA
  keypair, and both transactions and block proposals are genuinely
  signed and verified with it — but for a simple username/password UX
  (no seed phrases to write down), each node stores the private key
  alongside the account record on disk. Anyone with access to a node's
  `data/` folder can spend from any wallet known to that node, and if
  that wallet is a validator, propose blocks as them.
- **Trusted-peer replication.** Because it's meant to be *permissioned*
  and used by people who already trust each other, full account records
  — including the private key — are replicated between connected peer
  nodes. This is what lets you log in with the same username/password
  from any machine on the network. Don't connect a node as a peer to a
  machine you don't trust.
- **The validator whitelist lives only on the registry, never inside
  node-replicated data**, specifically so no node operator can grant
  themselves proposal rights by editing their own local files. See the
  "How consensus works" section above for why this matters.
- **Simple flood-based gossip**, not a full peer-discovery/gossip
  protocol. It works well for the small, mostly-fully-connected LAN
  topologies this is meant for; it is not battle-tested for large or
  adversarial networks.
- **Validator-set history isn't on-chain** — see the "known limitation"
  callout above.
- **Development web server.** Flask's built-in server (used by both the
  registry and every node) is fine for a LAN demo; it is not hardened
  for the public internet.
- **JSON-file storage**, not a real database. Simple, portable, and
  sufficient for a demo network of modest size; not built for high
  write-concurrency.

None of this stops the project from doing exactly what it's meant to do:
demonstrate, in a hands-on way, how a permissioned chain, wallets,
peer-to-peer propagation, and authority-based consensus fit together.
