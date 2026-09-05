# Permissioned Chain

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9%2B-blue?style=flat&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Flask-2.3%2B-black?style=flat&logo=flask&logoColor=white" alt="Flask">
  <img src="https://img.shields.io/badge/Jinja2-Templating-B41717?style=flat&logo=jinja&logoColor=white" alt="Jinja2">
  <img src="https://img.shields.io/badge/Werkzeug-Security-red?style=flat" alt="Werkzeug">
  <img src="https://img.shields.io/badge/ecdsa-secp256k1-blueviolet?style=flat" alt="ecdsa">
  <img src="https://img.shields.io/badge/requests-HTTP%2FP2P-green?style=flat&logo=python&logoColor=white" alt="requests">
  <img src="https://img.shields.io/badge/Storage-JSON%20files-lightgrey?style=flat" alt="Storage">
  <img src="https://img.shields.io/badge/HTML5%20%7C%20CSS3%20%7C%20JavaScript-Frontend-e34c26?style=flat&logo=html5&logoColor=white" alt="Frontend">
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat" alt="License: MIT">
</p>

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

This is the core mechanic the project is built around:

1. A miner switches to the **Miner** interface and clicks **Request Mining
   Certificate**. The node asks the MCA for a certificate, sending the
   current chain tip (block index + hash). The MCA mints a certificate
   that is:
   - bound to that miner's address,
   - bound to that *exact* next block index and *exact* previous hash,
   - signed with an HMAC secret shared across the network,
   - time-limited (expires after a few minutes by default),
   - single-use.
2. The miner clicks **Mine Block**. The node assembles pending
   transactions, attaches the certificate, and searches for a nonce whose
   block hash has the required number of leading zero hex digits (the
   light proof-of-work).
3. Once found, the node redeems the certificate with the MCA
   (`/verify_certificate`, `mark_used=true`). The MCA checks its own
   database: does this certificate exist, is the signature genuine, has
   it not expired, does it match this exact block position, and — has it
   already been used? Only if all of that passes does the MCA mark it
   used and confirm validity.
4. Only then does the node accept the block into its chain and broadcast
   it to its peers. Every peer that receives the block independently
   re-checks the certificate's signature *and* re-confirms with the MCA
   before accepting it too.

Because a certificate is single-use and tied to one specific block
position, a miner cannot mine two blocks with one certificate, cannot
reuse an old certificate once the chain has moved on, and cannot forge a
certificate without the shared HMAC secret. This is what makes "mining"
on this network permissioned, on top of the network already being
permissioned for viewing/transacting at the account level.

---

## Feature checklist against the original brief

- [x] Permissioned network — sign-up/login required to see or use the chain.
- [x] Every account starts with 50 coins.
- [x] Ordinary peer-to-peer transactions between users.
- [x] A separate "Miner" interface, reached by a button redirect from the
      wallet dashboard.
- [x] A Mining Certificate Authority that must be running for mining to
      work, issuing one certificate per block a miner wishes to mine.
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
- **Shared secrets in `config.py`.** `MCA_SECRET_KEY` is the thing that
  makes certificates un-forgeable. Treat it like a network password —
  change the default before using this beyond your own experiments, and
  keep it identical on the MCA and every node.
- **Development web server.** Flask's built-in server (used by both
  `mca_server.py` and `node_server.py`) is fine for a LAN demo; it is not
  hardened for the public internet.
- **JSON-file storage**, not a real database. Simple, portable, and
  sufficient for a demo network of modest size; not built for high
  write-concurrency.

None of this stops the project from doing exactly what it's meant to do:
demonstrate, in a hands-on way, how a permissioned chain, wallets, P2P
propagation, and a certificate-gated mining process fit together.
