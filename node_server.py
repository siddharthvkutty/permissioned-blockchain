"""
Blockchain node: wallet + miner web GUI, plus the peer-to-peer and
mining-certificate plumbing that ties nodes together into one network.

Run:
    python node_server.py
Env vars:
    PORT        port this node listens on (default 5000)
    MCA_URL     base URL of the Mining Certificate Authority (default http://localhost:6060)
    SECRET_KEY  Flask session secret (set a real one if exposing beyond your LAN)

Open http://localhost:<PORT> in a browser to sign up / log in.
"""
import os
import time
import uuid
from functools import wraps

import requests
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash

import config
import crypto_utils
from blockchain import Block, make_genesis_block, mine_block, meets_difficulty
from cert_utils import verify_signature as mca_verify_signature, CERT_FIELDS
from node_store import NodeStore

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

PORT = int(os.environ.get("PORT", 5000))
MCA_URL = os.environ.get("MCA_URL", config.DEFAULT_MCA_URL).rstrip("/")
SELF_URL = os.environ.get("SELF_URL", f"http://localhost:{PORT}")

store = NodeStore(os.path.join(DATA_DIR, f"node_{PORT}.json"))

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me-in-production")

# Ensure a genesis block exists.
if not store.get_chain():
    genesis = make_genesis_block()
    store.append_block(genesis.to_dict(), included_tx_ids=set())


# ============================================================ small helpers

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("address"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def current_account():
    addr = session.get("address")
    return store.get_account(addr) if addr else None


def tx_message(tx: dict) -> str:
    """Canonical string a transaction's signature is computed over."""
    return f"{tx['from']}|{tx['to']}|{tx['amount']}|{tx['timestamp']}|{tx['tx_id']}"


def is_valid_transaction(tx: dict, balance_hint: float = None) -> tuple:
    if tx["from"] == config.NETWORK_ADDRESS:
        return True, "ok"  # coinbase / reward, not signed by a wallet
    sender = store.get_account(tx["from"])
    if not sender:
        return False, "unknown sender"
    if not crypto_utils.verify(sender["pubkey"], tx_message(tx), tx.get("signature", "")):
        return False, "invalid signature"
    if tx["amount"] <= 0:
        return False, "non-positive amount"
    available = balance_hint if balance_hint is not None else store.get_balance(tx["from"])
    if available < tx["amount"]:
        return False, "insufficient balance"
    return True, "ok"


def broadcast(path: str, payload: dict, exclude: str = None):
    for peer in store.get_peers():
        if peer == exclude:
            continue
        try:
            requests.post(f"{peer}{path}", json=payload, timeout=3)
        except requests.RequestException:
            pass  # peer offline - fine for a demo LAN network


def get_mca_pubkey(force_refresh: bool = False):
    """Returns the MCA's public key, fetching it once and caching it
    locally (trust-on-first-use). Unlike the old shared-secret design,
    this value is not sensitive - it's only ever used to verify
    signatures, never to forge them - so caching it in plain JSON is fine.
    Returns None if it has never been fetched and the MCA is unreachable.
    """
    if not force_refresh:
        cached = store.get_cached_mca_pubkey()
        if cached:
            return cached
    try:
        r = requests.get(f"{MCA_URL}/public_key", timeout=5)
        if r.status_code == 200:
            pubkey = r.json().get("public_key")
            if pubkey:
                store.set_cached_mca_pubkey(pubkey)
                return pubkey
    except requests.RequestException:
        pass
    return store.get_cached_mca_pubkey()  # fall back to whatever we had, if anything


def validate_full_chain(chain: list) -> bool:
    """Local, self-contained validation of an entire chain: hash linkage,
    proof-of-work, and certificate authenticity (via the MCA's public
    key) for every block. Used when adopting a longer chain from a peer."""
    if not chain:
        return False
    genesis = chain[0]
    if genesis["index"] != 0 or genesis["previous_hash"] != "0" * 64:
        return False

    mca_pubkey = get_mca_pubkey()
    if not mca_pubkey and len(chain) > 1:
        return False  # can't verify certificates without the MCA's public key

    for i in range(1, len(chain)):
        prev = chain[i - 1]
        block = chain[i]
        if block["index"] != prev["index"] + 1:
            return False
        if block["previous_hash"] != prev["hash"]:
            return False

        b = Block.from_dict(block)
        if b.compute_hash() != block["hash"]:
            return False
        if not meets_difficulty(block["hash"], config.DIFFICULTY):
            return False

        cert = block.get("certificate")
        if not cert:
            return False
        payload = {k: cert[k] for k in CERT_FIELDS}
        if not mca_verify_signature(payload, cert.get("signature", ""), mca_pubkey):
            return False
        if cert["block_index"] != block["index"] or cert["prev_hash"] != block["previous_hash"]:
            return False
        if cert["miner_address"] != block.get("miner"):
            return False

    return True


def resolve_conflicts():
    """Longest-valid-chain rule: adopt a peer's chain if it's longer than
    ours and passes full validation."""
    local_chain = store.get_chain()
    best = None
    for peer in store.get_peers():
        try:
            r = requests.get(f"{peer}/p2p/chain", timeout=4)
            if r.status_code != 200:
                continue
            candidate = r.json().get("chain", [])
        except requests.RequestException:
            continue
        if len(candidate) > len(local_chain) and validate_full_chain(candidate):
            if best is None or len(candidate) > len(best):
                best = candidate
                local_chain = candidate
    if best:
        store.replace_chain(best)
        return True
    return False


# ================================================================== AUTH

@app.route("/")
def index():
    return redirect(url_for("dashboard") if session.get("address") else url_for("login"))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        if not username or not password:
            flash("Username and password are required.", "error")
            return render_template("signup.html")
        if password != confirm:
            flash("Passwords do not match.", "error")
            return render_template("signup.html")
        if store.get_account_by_username(username):
            flash("That username is already taken.", "error")
            return render_template("signup.html")

        privkey, pubkey = crypto_utils.generate_keypair()
        address = crypto_utils.address_from_pubkey(pubkey)
        account = store.create_account(username, password, address, pubkey, privkey)
        if account is None:
            flash("That username is already taken.", "error")
            return render_template("signup.html")

        # Let every connected peer know this account now exists, so the
        # same username/password can be used to log in from ANY node in
        # the network and transactions signed elsewhere can be verified
        # here. Full account records (including the private key) are
        # replicated between nodes because this is a *permissioned*
        # network of mutually-trusted machines - see README's "Security
        # model & limitations" section.
        broadcast("/p2p/accounts", {"account": account})

        session["address"] = address
        session["username"] = account["username"]
        flash(f"Welcome, {account['username']}! You've been granted {config.STARTING_BALANCE} coins.", "success")
        return redirect(url_for("dashboard"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        account = store.verify_login(username, password)
        if not account:
            flash("Invalid username or password.", "error")
            return render_template("login.html")
        session["address"] = account["address"]
        session["username"] = account["username"]
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# =============================================================== WALLET UI

@app.route("/dashboard")
@login_required
def dashboard():
    acc = current_account()
    address = acc["address"]
    balance = store.get_balance(address)
    spendable = store.get_spendable(address)

    others = [a for a in store.all_accounts() if a["address"] != address]

    history = []
    for block in reversed(store.get_chain()):
        for tx in block["transactions"]:
            if tx["from"] == address or tx["to"] == address:
                history.append({**tx, "block_index": block["index"], "confirmed": True})
    for tx in store.get_mempool():
        if tx["from"] == address or tx["to"] == address:
            history.append({**tx, "block_index": None, "confirmed": False})
    history = history[:30]

    return render_template(
        "dashboard.html",
        account=acc, balance=balance, spendable=spendable,
        others=others, history=history, port=PORT,
    )


@app.route("/send", methods=["POST"])
@login_required
def send():
    acc = current_account()
    to_username = request.form.get("to_username", "").strip()
    try:
        amount = float(request.form.get("amount", "0"))
    except ValueError:
        amount = 0

    recipient = store.get_account_by_username(to_username)
    if not recipient:
        flash("Unknown recipient.", "error")
        return redirect(url_for("dashboard"))
    if recipient["address"] == acc["address"]:
        flash("You can't send coins to yourself.", "error")
        return redirect(url_for("dashboard"))
    if amount <= 0:
        flash("Enter an amount greater than zero.", "error")
        return redirect(url_for("dashboard"))
    if store.get_spendable(acc["address"]) < amount:
        flash("Insufficient spendable balance (pending sends are reserved).", "error")
        return redirect(url_for("dashboard"))

    tx = {
        "tx_id": uuid.uuid4().hex,
        "from": acc["address"],
        "to": recipient["address"],
        "amount": round(amount, 8),
        "timestamp": time.time(),
    }
    tx["signature"] = crypto_utils.sign(acc["privkey"], tx_message(tx))

    store.add_to_mempool(tx)
    broadcast("/p2p/transactions", {"transaction": tx})
    flash(f"Sent {amount} coins to {recipient['username']}. Awaiting confirmation in a mined block.", "success")
    return redirect(url_for("dashboard"))


@app.route("/chain")
@login_required
def chain_view():
    chain = list(reversed(store.get_chain()))
    accounts_by_addr = {a["address"]: a["username"] for a in store.all_accounts()}
    accounts_by_addr[config.NETWORK_ADDRESS] = "NETWORK"
    return render_template("chain.html", chain=chain, names=accounts_by_addr)


@app.route("/peers", methods=["GET", "POST"])
@login_required
def peers_view():
    if request.method == "POST":
        if request.form.get("refresh_mca_key"):
            pubkey = get_mca_pubkey(force_refresh=True)
            if pubkey:
                flash("Refreshed the MCA's public key from the live service.", "success")
            else:
                flash("Could not reach the MCA to refresh its public key.", "error")
            return redirect(url_for("peers_view"))

        url = request.form.get("peer_url", "").strip().rstrip("/")
        if url:
            store.add_peer(url)
            try:
                # Tell the peer about us, then fully reconcile state in both
                # directions: pull their accounts/chain, push ours to them.
                requests.post(f"{url}/p2p/register", json={"url": SELF_URL}, timeout=4)

                r = requests.get(f"{url}/p2p/accounts", timeout=4)
                for remote_acc in r.json().get("accounts", []):
                    store.import_remote_account(remote_acc)

                for local_acc in store.all_accounts():
                    requests.post(f"{url}/p2p/accounts", json={"account": local_acc}, timeout=4)

                resolve_conflicts()
                requests.post(f"{url}/p2p/resolve", timeout=4)  # ask them to pull from us too
            except requests.RequestException:
                flash(f"Added {url}, but could not fully sync with it right now.", "error")
            else:
                flash(f"Connected and synced with peer {url}.", "success")
    return render_template(
        "peers.html", peers=store.get_peers(), self_url=SELF_URL, mca_url=MCA_URL,
        mca_pubkey=store.get_cached_mca_pubkey(),
    )


# =============================================================== MINER UI

@app.route("/miner")
@login_required
def miner():
    tip = store.get_tip()
    cert = session.get("active_cert")
    cert_stale = bool(cert and tip and (cert["block_index"] != tip["index"] + 1 or cert["prev_hash"] != tip["hash"]))
    if cert_stale:
        session.pop("active_cert", None)
        cert = None

    acc = current_account()
    is_validator = None  # None means "couldn't reach the MCA to check"
    try:
        r = requests.get(f"{MCA_URL}/validators", timeout=3)
        if r.status_code == 200:
            is_validator = acc["address"] in r.json().get("validators", {})
    except requests.RequestException:
        pass

    return render_template(
        "miner.html",
        account=acc, tip=tip, cert=cert, is_validator=is_validator,
        difficulty=config.DIFFICULTY, reward=config.MINING_REWARD, mca_url=MCA_URL,
    )


@app.route("/miner/certificate", methods=["POST"])
@login_required
def miner_certificate():
    acc = current_account()
    tip = store.get_tip()
    try:
        r = requests.post(f"{MCA_URL}/request_certificate", json={
            "miner_address": acc["address"],
            "block_index": tip["index"] + 1,
            "prev_hash": tip["hash"],
        }, timeout=5)
    except requests.RequestException as e:
        return jsonify({"ok": False, "error": f"Could not reach MCA at {MCA_URL}: {e}"}), 502

    if r.status_code != 200:
        return jsonify({"ok": False, "error": f"MCA rejected the request: {r.text}"}), 400

    cert = r.json().get("certificate")
    session["active_cert"] = cert
    return jsonify({"ok": True, "certificate": cert})


@app.route("/miner/mine", methods=["POST"])
@login_required
def miner_mine():
    acc = current_account()
    cert = session.get("active_cert")
    tip = store.get_tip()

    if not cert:
        return jsonify({"ok": False, "error": "No active certificate. Request one first."}), 400
    if cert["block_index"] != tip["index"] + 1 or cert["prev_hash"] != tip["hash"]:
        session.pop("active_cert", None)
        return jsonify({"ok": False, "error": "Certificate is stale (chain moved on). Request a new one."}), 409

    # Pick valid, affordable mempool transactions (simple sequential balance check).
    running_balance = {}
    selected = []
    for tx in store.get_mempool():
        bal = running_balance.get(tx["from"], store.get_balance(tx["from"]))
        ok, _ = is_valid_transaction(tx, balance_hint=bal)
        if ok:
            running_balance[tx["from"]] = bal - tx["amount"]
            selected.append(tx)

    reward_tx = {
        "tx_id": uuid.uuid4().hex,
        "from": config.NETWORK_ADDRESS,
        "to": acc["address"],
        "amount": config.MINING_REWARD,
        "timestamp": time.time(),
        "signature": None,
        "note": "mining reward",
    }

    block = Block(
        index=cert["block_index"],
        timestamp=time.time(),
        transactions=selected + [reward_tx],
        previous_hash=cert["prev_hash"],
        certificate=cert,
        miner=acc["address"],
    )

    def tip_moved():
        current_tip = store.get_tip()
        return current_tip["hash"] != cert["prev_hash"]

    mined = mine_block(block, config.DIFFICULTY, stop_check=tip_moved)
    if mined is None:
        return jsonify({"ok": False, "error": "Chain moved on while mining. Request a new certificate."}), 409

    # Redeem the certificate with the MCA - the authoritative double-check.
    try:
        r = requests.post(f"{MCA_URL}/verify_certificate", json={
            "certificate": cert, "mark_used": True,
        }, timeout=5)
        result = r.json()
    except requests.RequestException as e:
        return jsonify({"ok": False, "error": f"Could not reach MCA to redeem certificate: {e}"}), 502

    if not result.get("valid"):
        return jsonify({"ok": False, "error": f"Certificate rejected by MCA: {result.get('reason')}"}), 400

    # Final tip check (race with another miner or an incoming p2p block).
    current_tip = store.get_tip()
    if current_tip["hash"] != cert["prev_hash"]:
        return jsonify({"ok": False, "error": "Someone else's block arrived first. Request a new certificate."}), 409

    included_ids = {t["tx_id"] for t in selected}
    store.append_block(mined.to_dict(), included_tx_ids=included_ids)
    session.pop("active_cert", None)
    broadcast("/p2p/blocks", {"block": mined.to_dict()}, exclude=None)

    return jsonify({"ok": True, "block": mined.to_dict(), "reward": config.MINING_REWARD})


# ================================================================ P2P API

@app.route("/p2p/register", methods=["POST"])
def p2p_register():
    body = request.get_json(force=True, silent=True) or {}
    url = (body.get("url") or "").rstrip("/")
    if not url:
        return jsonify({"error": "url required"}), 400
    store.add_peer(url)
    return jsonify({"ok": True, "peers": store.get_peers()})


@app.route("/p2p/accounts", methods=["GET", "POST"])
def p2p_accounts():
    if request.method == "GET":
        return jsonify({"accounts": store.all_accounts()})
    body = request.get_json(force=True, silent=True) or {}
    account = body.get("account")
    if not account:
        return jsonify({"error": "account required"}), 400
    added = store.import_remote_account(account)
    return jsonify({"ok": True, "added": added})


@app.route("/p2p/transactions", methods=["POST"])
def p2p_transactions():
    body = request.get_json(force=True, silent=True) or {}
    tx = body.get("transaction")
    if not tx:
        return jsonify({"error": "transaction required"}), 400
    ok, reason = is_valid_transaction(tx)
    if not ok:
        return jsonify({"ok": False, "reason": reason}), 400
    store.add_to_mempool(tx)
    return jsonify({"ok": True})


@app.route("/p2p/blocks", methods=["POST"])
def p2p_blocks():
    body = request.get_json(force=True, silent=True) or {}
    block = body.get("block")
    if not block:
        return jsonify({"error": "block required"}), 400

    tip = store.get_tip()

    if block["index"] == tip["index"] + 1 and block["previous_hash"] == tip["hash"]:
        b = Block.from_dict(block)
        if b.compute_hash() != block["hash"] or not meets_difficulty(block["hash"], config.DIFFICULTY):
            return jsonify({"ok": False, "reason": "invalid proof-of-work"}), 400

        cert = block.get("certificate") or {}
        payload = {k: cert.get(k) for k in CERT_FIELDS}
        mca_pubkey = get_mca_pubkey()
        if not mca_verify_signature(payload, cert.get("signature", ""), mca_pubkey):
            return jsonify({"ok": False, "reason": "invalid certificate signature"}), 400
        if cert.get("block_index") != block["index"] or cert.get("prev_hash") != block["previous_hash"]:
            return jsonify({"ok": False, "reason": "certificate does not match block position"}), 400

        # Authoritative check that the MCA really has this certificate on
        # record as used (it should already be marked used by the miner).
        try:
            r = requests.post(f"{MCA_URL}/verify_certificate", json={
                "certificate": cert, "mark_used": False,
            }, timeout=5)
            result = r.json()
        except requests.RequestException:
            result = {"valid": False, "reason": "MCA unreachable"}

        if not (result.get("valid") or result.get("reason") == "certificate already used"):
            return jsonify({"ok": False, "reason": f"MCA rejected certificate: {result.get('reason')}"}), 400

        included_ids = {t["tx_id"] for t in block["transactions"]}
        store.append_block(block, included_tx_ids=included_ids)
        broadcast("/p2p/blocks", {"block": block})  # simple flood to our own peers
        return jsonify({"ok": True})

    if block["index"] > tip["index"] + 1:
        # We're behind - try to catch up from whoever sent this.
        resolve_conflicts()
        return jsonify({"ok": True, "note": "resolved via chain sync"})

    return jsonify({"ok": False, "reason": "block does not extend our chain tip"}), 409


@app.route("/p2p/chain")
def p2p_chain():
    return jsonify({"chain": store.get_chain(), "length": len(store.get_chain())})


@app.route("/p2p/resolve", methods=["POST"])
def p2p_resolve():
    changed = resolve_conflicts()
    return jsonify({"changed": changed, "length": len(store.get_chain())})


@app.route("/status")
def status():
    tip = store.get_tip()
    return jsonify({
        "port": PORT, "chain_length": len(store.get_chain()),
        "tip_hash": tip["hash"] if tip else None,
        "peers": store.get_peers(), "mempool_size": len(store.get_mempool()),
        "mca_url": MCA_URL,
    })


if __name__ == "__main__":
    print(f"[Node] Listening on 0.0.0.0:{PORT}  (open http://localhost:{PORT} in a browser)")
    print(f"[Node] Using MCA at {MCA_URL}")
    print(f"[Node] Data file: {store.path}")
    app.run(host="0.0.0.0", port=PORT, threaded=True)
