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
and node-to-registry HTTP calls), and `ecdsa` (real wallet and block-signing
cryptography).

## 3. Quickest possible test drive (all on one machine)

Open **two terminals**.

**Terminal 1 — start the validator registry:**

```bash
# Linux/macOS
./run_mca.sh
# Windows
run_mca.bat
```

You should see:
```
[MCA] Validator registry listening on 0.0.0.0:6060
```
Leave this running. Visit `http://localhost:6060` in a browser any time
to see the current validator list and rotation order.

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
[Node] Using validator registry (MCA) at http://localhost:6060
```

Now open **http://localhost:5000** in your browser.

1. Click **Create a wallet**, pick a username/password, sign up. You're
   granted 50 coins and land on the **Wallet** dashboard.
2. Open a **second browser tab** (or a private/incognito window) to
   `http://localhost:5000` and sign up as a second user, e.g. `bob`.
3. **Approve at least one of them as a validator** — nobody can propose
   blocks until this happens. See section 3.5 below.
4. As `bob`, go to the wallet dashboard and send some coins to your first
   user.
5. Whoever's actually up next in the rotation clicks **Switch to
   Validator Interface**, sees "It's your turn," and clicks **Propose
   Block**. This is close to instant — there's no puzzle to solve.
6. Go back to the **Wallet** tab and refresh — you'll see the new
   balance and the confirmed transaction. Check the **Chain** page to see
   the full block-by-block ledger, including who proposed each block.

### 3.5 Approving validators (required before anyone can propose blocks)

Signing up gives you a wallet, but **nobody can propose a block until the
network admin explicitly approves their address** — and the *order*
they're approved in becomes the rotation order everyone uses.

1. On the machine you signed up on, go to the **Wallet** dashboard — your
   address is shown right under your balance. Copy it.
2. Go to the registry's admin page:
   `http://localhost:6060/admin/validators` (or
   `http://<registry-ip>:6060/admin/validators` from another machine).
3. Enter the **admin key** (`MCA_ADMIN_KEY` — see section 5 for how to
   set this), paste the address, optionally add a label, and click
   **Approve as validator**.
4. Repeat for anyone else you want in the rotation. The **first** address
   you approve gets position 0 in the rotation, the second gets position
   1, and so on.
5. Back on that user's **Validator** page, they'll now see whether it's
   currently their turn, and can propose when it is.

To revoke someone's ability to propose later, go back to the same page,
paste their address, and click **Revoke** — this takes effect
immediately (their next proposal attempt will be rejected, and the
rotation simply skips their old position going forward).

**Set the admin key before anyone relies on this**, since it defaults to
a placeholder value:

```bash
# Linux/macOS
export MCA_ADMIN_KEY="something-only-the-admin-knows"
./run_mca.sh

# Windows
set MCA_ADMIN_KEY=something-only-the-admin-knows
run_mca.bat
```

## 4. Running it across multiple machines on the same network

This is the setup the project is actually designed for: one registry,
and one node per participating machine, all on the same LAN.

### 4.1 Pick one machine to host the registry

On that machine, find its LAN IP address:

```bash
# Linux/macOS
ip addr show          # or: ifconfig
# Windows
ipconfig
```

Say it's `192.168.1.10`. Start the registry there:

```bash
./run_mca.sh            # Linux/macOS
run_mca.bat              # Windows
```

It listens on port `6060` on all network interfaces, so it's reachable at
`http://192.168.1.10:6060` from any other machine on the LAN.

**Nothing to synchronize secretly this time** — there's no shared secret
or keypair to distribute at all. Every node just needs to be able to
reach the registry's URL over HTTP; the validator list itself is public,
read-only information any node can fetch freely.

### 4.2 On every participating machine, run a node

Each machine picks its own port (5000 is a fine default if only one node
runs per machine) and points at the registry's address:

```bash
# Linux/macOS
./run_node.sh 5000 http://192.168.1.10:6060

# Windows
run_node.bat 5000 http://192.168.1.10:6060
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
eventually reach everyone. For small networks, connecting every node to
every other node ("full mesh") is simplest and most reliable.

### 4.4 Everyday use after that

- Anyone can sign up/log in from **any** node in the network (accounts
  are replicated once nodes are peered).
- Sending coins from any node's Wallet page broadcasts the transaction to
  the whole network; it shows as **pending** until it's included in a
  proposed block.
- Only the validator whose turn it currently is can propose the next
  block — everyone else's Validator page simply shows whose turn it is
  and waits. There's no competition to game.

## 5. Tuning the network

All of these live in `config.py` and can also be overridden with
environment variables:

| Setting | Env var | Default | What it does |
|---|---|---|---|
| Block-proposal reward | `BLOCK_REWARD` | `10` | Coins paid to whoever proposes an accepted block. |
| Starting balance | `STARTING_BALANCE` | `50` | Coins granted at signup. |
| Slot timeout | `SLOT_TIMEOUT` | `30` | Seconds a slot stays reserved for its primary validator before eligibility falls through to the next one in rotation. Lower it for faster recovery from an offline validator in testing; keep it comfortably above normal network latency in real use so honest proposers aren't skipped over prematurely. |
| Max clock skew | `MAX_CLOCK_SKEW` | `10` | How far into the future a block's self-reported timestamp is allowed to be before it's rejected outright, to prevent gaming the timeout fallback with a dishonest timestamp. |
| Admin key | `MCA_ADMIN_KEY` | *(placeholder — change this)* | Needed only to approve/revoke validators on the registry; not distributed to nodes. |

Example — run the registry with a real admin key:

```bash
MCA_ADMIN_KEY="my-real-admin-key" ./run_mca.sh
```

## 6. Running more than one node on the same machine (for testing)

Data files are named by port (`data/node_<port>.json`), so you can run
several nodes on one machine to try out multi-node behavior without a
second computer:

```bash
./run_node.sh 5000 http://localhost:6060
./run_node.sh 5001 http://localhost:6060   # in another terminal
```

Then peer `http://localhost:5000` with `http://localhost:5001` from
either node's Peers page.

## 7. Resetting the network

Each node and the registry keep all their state in the `data/` folder,
one JSON file per port. To wipe a node or the registry back to a blank
slate, stop it and delete the relevant file, e.g. `data/node_5000.json`
or `data/mca_6060.json`. If you reset one node in a network that has
peers with existing history, reconnect it on the **Peers** page
afterward so it re-syncs the current accounts and chain instead of
starting an incompatible fork. If you reset the registry itself, every
node's cached validator list will still work briefly from cache, but
nobody new can be approved and existing approvals are gone — you'll need
to re-approve validators (in the same order, if you want to preserve the
existing rotation exactly) before proposals can continue.

## 8. Troubleshooting

- **A validator seems permanently stuck / nobody can propose** — this
  shouldn't happen: after `SLOT_TIMEOUT` seconds with no block, any other
  validator becomes eligible automatically (see README's "Liveness"
  section). If it persists longer than that, check that the stalled
  validator's node isn't the one everyone else is trying to peer
  through, and confirm `SLOT_TIMEOUT` is set to the same value
  everywhere (it doesn't strictly need to match across nodes for
  correctness, but very different values will make the Validator page's
  displayed countdown misleading on nodes with a different setting).
- **"It's not your turn" even though you think it should be** —
  double-check the rotation order on the registry's dashboard
  (`http://<registry-ip>:6060`). Position is determined purely by
  approval order; if someone else was approved before you, they're ahead
  of you in the cycle. This is expected, not a bug.
- **"No validators are approved yet"** — see section 3.5. Nobody can
  propose anything until an admin approves at least one address.
- **A peer never shows up on the Peers list / accounts don't sync** —
  confirm the peer URL is reachable from the browser's machine (try
  opening it directly, e.g. `http://192.168.1.11:5000/status`), and that
  both machines allow inbound connections on the node's port (5000 by
  default) through their firewall.
- **A block you proposed didn't reach other nodes** — check your node's
  Peers page to confirm it's actually connected to them; broadcasting
  only reaches nodes you've peered with.
- **Can't reach the registry's port at all** — some browsers (Chrome
  included) block certain ports outright for historical protocol-safety
  reasons regardless of what's running there. Port 6060 (this project's
  default) is not on that blocklist, but if you've changed it to
  something else, double check it isn't accidentally landing on a
  blocked port.
