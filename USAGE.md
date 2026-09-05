# USAGE.md

Step-by-step instructions to install, run, and use the Permissioned Chain
network — both on a single machine (for trying it out) and across
multiple machines on a LAN (the intended setup).

## 1. Requirements

- Python 3.9+ (Linux, Windows, or macOS)
- pip

Check your Python version:

```bash
python3 --version        # Linux/macOS
python --version         # Windows
```

## 2. Install dependencies

From inside the project folder:

```bash
# Linux / macOS
pip install -r requirements.txt --break-system-packages
# (drop --break-system-packages if you're using a virtualenv, which is recommended:
#   python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt)

# Windows (Command Prompt or PowerShell)
pip install -r requirements.txt
```

This installs `Flask` (the web GUI/server), `requests` (used for node-to-node
and node-to-MCA HTTP calls), and `ecdsa` (real wallet cryptography).

## 3. Quickest possible test drive (all on one machine)

Open **two terminals**.

**Terminal 1 — start the Mining Certificate Authority:**

```bash
# Linux/macOS
./run_mca.sh
# Windows
run_mca.bat
```

You should see:
```
[MCA] Mining Certificate Authority listening on 0.0.0.0:6000
```
Leave this running. You can check it's alive by visiting
`http://localhost:6000` in a browser — it shows a simple live list of
issued certificates.

**Terminal 2 — start a node:**

```bash
# Linux/macOS
./run_node.sh
# Windows
run_node.bat
```

You should see:
```
[Node] Listening on 0.0.0.0:5000  (open http://localhost:5000 in a browser)
[Node] Using MCA at http://localhost:6000
```

Now open **http://localhost:5000** in your browser.

1. Click **Create a wallet**, pick a username/password, sign up. You're
   granted 50 coins and land on the **Wallet** dashboard.
2. Open a **second browser tab** (or a private/incognito window) to
   `http://localhost:5000` and sign up as a second user, e.g. `bob`.
3. As `bob`, go to the wallet dashboard and send some coins to your first
   user.
4. As your first user, click **Switch to Miner Interface**.
5. Click **Request Mining Certificate** — this calls the MCA and gets you
   a one-time permission slip for the next block.
6. Click **Mine Block** — the browser calls the node, which runs a light
   proof-of-work (should take well under a few seconds), redeems the
   certificate with the MCA, and — if everything checks out — appends the
   block, paying you the mining reward and confirming `bob`'s transaction.
7. Go back to the **Wallet** tab and refresh — you'll see your new
   balance and the confirmed transaction. Check the **Chain** page to see
   the full block-by-block ledger.

## 4. Running it across multiple machines on the same network

This is the setup the project is actually designed for: one MCA, and one
node per participating machine, all on the same LAN.

### 4.1 Pick one machine to host the MCA

On that machine, find its LAN IP address:

```bash
# Linux/macOS
ip addr show          # or: ifconfig
# Windows
ipconfig
```

Say it's `192.168.1.10`. Start the MCA there:

```bash
./run_mca.sh            # Linux/macOS
run_mca.bat             # Windows
```

It listens on port `6000` on all network interfaces, so it's reachable at
`http://192.168.1.10:6000` from any other machine on the LAN.

**Important:** every machine must use the *same* `MCA_SECRET_KEY`. Either:

- edit `config.py` on every machine to use the same custom secret before
  distributing the project, **or**
- set the environment variable before launching the MCA and every node,
  e.g. (Linux/macOS) `export MCA_SECRET_KEY="my-network-secret"` or
  (Windows) `set MCA_SECRET_KEY=my-network-secret`.

### 4.2 On every participating machine, run a node

Each machine picks its own port (5000 is a fine default if only one node
runs per machine) and points at the MCA's address:

```bash
# Linux/macOS
./run_node.sh 5000 http://192.168.1.10:6000

# Windows
run_node.bat 5000 http://192.168.1.10:6000
```

Then open `http://localhost:5000` in a browser on that machine and sign
up / log in as usual.

### 4.3 Connect the nodes to each other

On each node's **Peers** page (`http://localhost:5000/peers`), enter the
address of at least one other node on the network, e.g.
`http://192.168.1.11:5000`, and click **Connect**. This:

- registers each node with the other,
- syncs existing accounts both ways (so people who signed up on one
  machine show up as valid recipients — and can log in — on the others),
- syncs the blockchain (adopting the longer valid chain if the two nodes
  had diverged).

You don't have to connect every node to every other node — as long as the
nodes form a connected graph, accounts/transactions/blocks will
eventually reach everyone (each node re-broadcasts what it receives to
its own peers). For small networks, connecting every node to every other
node ("full mesh") is simplest and most reliable.

### 4.4 Everyday use after that

- Anyone can sign up/log in from **any** node in the network (accounts
  are replicated once nodes are peered).
- Sending coins from any node's Wallet page broadcasts the transaction to
  the whole network; it shows as **pending** until someone mines a block
  that includes it.
- Anyone can switch to their local node's **Miner** interface, request a
  certificate, and mine — whoever gets there first with a valid block
  wins that block's reward; certificates for stale block positions are
  automatically rejected so this can't be gamed.

## 5. Tuning the network

All of these live in `config.py` and can also be overridden with
environment variables (useful for quick experiments without editing
files):

| Setting | Env var | Default | What it does |
|---|---|---|---|
| Proof-of-work difficulty | `CHAIN_DIFFICULTY` | `5` | Leading hex zeros required in a block hash. Higher = slower mining. ~4-5 keeps it to a fraction of a second up to a couple of seconds on a normal desktop; go higher only if your hardware is unusually fast. |
| Mining reward | `MINING_REWARD` | `10` | Coins paid for every accepted block. |
| Starting balance | `STARTING_BALANCE` | `50` | Coins granted at signup. |
| Certificate validity | `CERT_VALIDITY_SECONDS` | `300` | How long a mining certificate stays redeemable. |
| Shared secret | `MCA_SECRET_KEY` | *(placeholder — change this)* | Must match on the MCA and every node. |

Example — run a node with a harder difficulty just for testing:

```bash
CHAIN_DIFFICULTY=6 ./run_node.sh 5000 http://localhost:6000
```

## 6. Running more than one node on the same machine (for testing)

Data files are named by port (`data/node_<port>.json`), so you can run
several nodes on one machine to try out multi-node behavior without a
second computer:

```bash
./run_node.sh 5000 http://localhost:6000
./run_node.sh 5001 http://localhost:6000   # in another terminal
```

Then peer `http://localhost:5000` with `http://localhost:5001` from
either node's Peers page.

## 7. Resetting the network

Each node and the MCA keep all their state in the `data/` folder, one
JSON file per port. To wipe a node or the MCA back to a blank slate, stop
it and delete the relevant file, e.g. `data/node_5000.json` or
`data/mca_6000.json`. If you reset one node in a network that has peers
with existing history, reconnect it on the **Peers** page afterward so it
re-syncs the current accounts and chain instead of starting an
incompatible fork.

## 8. Troubleshooting

- **"Could not reach MCA"** on the Miner page — check the MCA is running
  and that the node was started with the correct `MCA_URL` / `--mca-url`
  pointing at it (including the right IP if it's on another machine), and
  that no firewall is blocking port 6000.
- **A peer never shows up on the Peers list / accounts don't sync** —
  confirm the peer URL is reachable from the browser's machine (try
  opening it directly, e.g. `http://192.168.1.11:5000/status`), and that
  both machines allow inbound connections on the node's port (5000 by
  default) through their firewall.
- **"Certificate is stale (chain moved on)"** when mining — someone else
  mined a block after you requested your certificate. This is expected
  and by design; just click **Request Mining Certificate** again.
- **Mining feels slow** — lower `CHAIN_DIFFICULTY` (see section 5).
