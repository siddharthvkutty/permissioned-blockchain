# Permissioned Chain

A small, self-contained **permissioned blockchain network** with a real web
GUI, built with Python and Flask. It works on Linux and Windows (anywhere
Python 3 runs) and is designed to be run across multiple machines on the
same LAN.

- **Permissioned**: nobody can see or use the chain without an account.
- **Wallets for everyone**: sign up and you're instantly granted 50 coins.
- **Ordinary transactions**: send coins to any other user on the network.
- **Mining requires a certificate**: to mine, you switch to a separate
  "Miner" interface, request a one-time-use *mining certificate* from a
  dedicated **Mining Certificate Authority (MCA)** service, and only a
  block that carries a certificate the MCA recognizes as valid (and
  unused) will be accepted by the network.
- **Light proof-of-work**: tuned so a normal desktop mines a block in
  well under a few seconds.
- **Constant mining reward**: every accepted block pays the same reward.

---

## How it fits together

There are two kinds of service in this project:

```
                     ┌─────────────────────────┐
                     │  Mining Certificate      │
                     │  Authority (MCA)         │   <- one per network,
                     │  mca_server.py           │      must stay running
                     └───────────┬──────────────┘
                                 │  issue / verify certificates
                 ┌───────────────┼────────────────┐
                 │               │                │
        ┌────────▼───────┐ ┌─────▼──────────┐ ┌───▼────────────┐
        │ Node (machine A)│ │ Node (machine B)│ │ Node (machine C)│
        │ node_server.py  │ │ node_server.py  │ │ node_server.py  │
        │ Wallet + Miner  │◄┼─Peers, sync────►│ │ Wallet + Miner  │
        │ web GUI         │ │ web GUI         │ │ web GUI         │
        └─────────────────┘ └─────────────────┘ └─────────────────┘
```

- **`mca_server.py`** — the Mining Certificate Authority. It has no login;
  it's an internal service other machines talk to. It must be running in
  the background for anyone to be able to mine. Run exactly one per
  network.
- **`node_server.py`** — the program each person on the network actually
  uses. It serves the wallet dashboard and the miner interface as a normal
  web page (open it in any browser — this is what makes it work
  identically on Linux and Windows). Run one instance per machine/person.
  Nodes register with each other as **peers** and gossip accounts,
  transactions, and blocks so everyone converges on the same ledger.

See **[USAGE.md](USAGE.md)** for exact step-by-step commands to run all of
this, including multi-machine setup.

---

## How mining is "permissioned"

This project actually layers **two separate permission systems**, which is
the main thing that distinguishes it from "a blockchain with a login
screen":

- **Network membership** (handled by each node): you need an account to
  see or transact on the chain at all. Anyone can sign up and get a
  wallet with 50 starting coins.
- **Validator admission** (handled centrally by the MCA): being a member
  does **not** automatically mean you're allowed to mine. A separate,
  admin-controlled whitelist on the MCA decides which specific wallet
  addresses are authorized validators. Everyone else's certificate
  requests are rejected outright, however good their proof-of-work would
  be.

This mirrors how real permissioned-blockchain platforms (e.g. Hyperledger
Fabric's Membership Service Provider) separate "who can use the network"
from "who can participate in producing blocks." A network administrator
manages this at the MCA's `/admin/validators` page using a dedicated
admin key (`MCA_ADMIN_KEY` in `config.py`) — known only to whoever
governs network membership, never distributed to nodes.

**Why this lives on the MCA and not inside node data:** account records
(including roles, if they were stored there) are replicated between
trusted peer nodes so people can log in from any machine. If "who's
allowed to mine" were just a field on that same replicated account
record, any node operator could simply edit their own local JSON file to
grant themselves validator status — completely defeating the point.
Keeping the validator whitelist only on the MCA, a separately-run service
most miners don't have filesystem access to, is what makes the admission
control actually mean something.

The full mining flow, then:

1. On the **Miner** page, a wallet holder sees whether the MCA currently
   recognizes their address as an authorized validator.
2. If authorized, they click **Request Mining Certificate**. The MCA
   checks the whitelist *before* issuing anything; unauthorized addresses
   are rejected with a clear reason and never receive a certificate.
3. If issued, the certificate is bound to that miner's address, that
   *exact* next block index and previous hash, signed with the MCA's own
   ECDSA private key (generated once, never leaving the MCA's machine),
   time-limited, and single-use.
4. The miner clicks **Mine Block**. The node assembles pending
   transactions, attaches the certificate, and searches for a nonce whose
   block hash has the required number of leading zero hex digits (the
   light proof-of-work).
5. Once found, the node redeems the certificate with the MCA
   (`/verify_certificate`, `mark_used=true`). The MCA re-checks
   everything — signature authenticity, expiry, exact block-position
   match, single-use, **and validator status again** (in case it was
   revoked mid-mining) — before marking it used and confirming validity.
6. Only then does the node accept the block and broadcast it to peers.
   Every peer independently re-verifies the certificate's signature *and*
   re-confirms with the MCA before accepting the block too.

Because a certificate is single-use, position-bound, and gated by a
centrally-managed validator whitelist, a non-validator cannot mine at
all, an authorized miner cannot reuse a stale certificate, and nobody can
forge a certificate without the MCA's private key — which, unlike the
project's earlier design, never has to be distributed anywhere.

---

## Feature checklist against the original brief

- [x] Permissioned network — sign-up/login required to see or use the chain.
- [x] Every account starts with 50 coins.
- [x] Ordinary peer-to-peer transactions between users.
- [x] A separate "Miner" interface, reached by a button redirect from the
      wallet dashboard.
- [x] A Mining Certificate Authority that must be running for mining to
      work, issuing one certificate per block a miner wishes to mine.
- [x] A centrally-administered validator whitelist on the MCA — being a
      network member does not automatically mean you're allowed to mine.
- [x] Certificates are checked against the MCA's own database when a
      block is published (not just checked locally).
- [x] Multiple machines on the same network can connect, sign up/log in,
      transact, and mine.
- [x] Constant mining rewards.
- [x] Deliberately light proof-of-work (configurable, defaults to a
      fraction of a second up to a couple of seconds on a normal desktop).
- [x] A proper (browser-based) GUI that runs the same way on Linux and
      Windows.

---

## Project layout

```
permissioned-blockchain/
├── config.py          shared network parameters (difficulty, reward, MCA secret...)
├── crypto_utils.py     ECDSA keypair generation / signing / verification
├── blockchain.py       Block structure + light proof-of-work
├── mca_store.py        certificate storage + HMAC signing for the MCA
├── mca_server.py        <- run this to start the Mining Certificate Authority
├── node_store.py       account/chain/mempool/peer storage for a node
├── node_server.py       <- run this to start a wallet + miner node
├── templates/          Jinja2 HTML templates for the web GUI
├── static/              CSS + JS for the web GUI
├── run_mca.sh / .bat    convenience launchers for the MCA
├── run_node.sh / .bat   convenience launchers for a node
├── requirements.txt
└── USAGE.md             step-by-step instructions
```

---

## Security model & limitations (read this before using it for anything real)

This project is a teaching/demo network, not production financial
infrastructure. Specifically, by design:

- **Custodial-style key storage.** Signing up generates a real ECDSA
  keypair, and transactions are genuinely signed and verified with it —
  but for a simple username/password UX (no seed phrases to write down),
  each node stores the private key alongside the account record on disk.
  Anyone with access to a node's `data/` folder can spend from any wallet
  known to that node.
- **Trusted-peer replication.** Because it's meant to be *permissioned*
  and used by people who already trust each other (e.g. a class, a team,
  a LAN party), full account records — including the private key — are
  replicated between connected peer nodes. This is what lets you log in
  with the same username/password from any machine on the network. Don't
  connect a node as a peer to a machine you don't trust.
- **Simple flood-based gossip**, not a full peer-discovery/gossip
  protocol. It works well for the small, mostly-fully-connected LAN
  topologies this is meant for (star or mesh of a handful of machines);
  it is not battle-tested for large or adversarial networks.
- **Shared secrets in `config.py`.** As of this version, there is no
  longer a shared signing secret to protect — an earlier design used one
  symmetric HMAC secret copied onto every node, which meant a single
  leaked node could let an attacker forge certificates for the whole
  network. Certificates are now signed with the MCA's own ECDSA keypair;
  only its public key (safe to share, cannot be used to forge anything)
  is distributed to nodes. `MCA_ADMIN_KEY` is the one remaining secret in
  `config.py`, and it's only needed by the MCA itself to gate the
  validator-admission page — never distribute it to node operators.
- **Development web server.** Flask's built-in server (used by both
  `mca_server.py` and `node_server.py`) is fine for a LAN demo; it is not
  hardened for the public internet.
- **JSON-file storage**, not a real database. Simple, portable, and
  sufficient for a demo network of modest size; not built for high
  write-concurrency.

None of this stops the project from doing exactly what it's meant to do:
demonstrate, in a hands-on way, how a permissioned chain, wallets, P2P
propagation, and a certificate-gated mining process fit together.
