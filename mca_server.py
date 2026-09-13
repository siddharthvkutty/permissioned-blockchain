"""
Mining Certificate Authority (MCA) server.

Run one of these per network (it's the "central" service that must be
running in the background). Miners request a certificate from it before
mining each block, and nodes double-check every submitted block's
certificate against this service's database before accepting the block.

Run:
    python mca_server.py
Env vars:
    MCA_PORT       (default 6060)
    MCA_ADMIN_KEY  required to manage the validator whitelist at /admin/validators
                   (see config.py - do not distribute this to node operators)
"""
import hmac
import os
import time

from flask import Flask, jsonify, request, render_template

import config
from mca_store import MCAStore

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

PORT = int(os.environ.get("MCA_PORT", 6060))
store = MCAStore(os.path.join(DATA_DIR, f"mca_{PORT}.json"))

app = Flask(__name__)


@app.route("/status")
def status():
    return jsonify({
        "service": "Mining Certificate Authority",
        "status": "online",
        "port": PORT,
        "certificates_issued": len(store.data["certificates"]),
    })


@app.route("/public_key")
def public_key():
    """Safe to call from anywhere with no auth - this is the MCA's PUBLIC
    key. Every node needs it to verify certificate signatures; unlike the
    old shared-secret design, handing this out cannot help anyone forge a
    certificate."""
    return jsonify({"public_key": store.get_public_key()})


@app.route("/request_certificate", methods=["POST"])
def request_certificate():
    body = request.get_json(force=True, silent=True) or {}
    miner_address = body.get("miner_address")
    block_index = body.get("block_index")
    prev_hash = body.get("prev_hash")

    if not miner_address or block_index is None or not prev_hash:
        return jsonify({"error": "miner_address, block_index and prev_hash are required"}), 400

    if not store.is_validator(miner_address):
        return jsonify({
            "error": "This address is not an authorized validator. "
                     "Ask the network administrator to approve it on the MCA's Validators page before you can mine."
        }), 403

    cert = store.issue_certificate(miner_address, int(block_index), prev_hash)
    return jsonify({"certificate": cert})


@app.route("/verify_certificate", methods=["POST"])
def verify_certificate():
    body = request.get_json(force=True, silent=True) or {}
    submitted = body.get("certificate") or {}
    mark_used = bool(body.get("mark_used", False))

    valid, reason, record = store.evaluate(submitted, mark_used)
    return jsonify({"valid": valid, "reason": reason, "certificate": record})


@app.route("/certificates")
def certificates_json():
    return jsonify({"certificates": store.all_certificates()})


@app.route("/validators")
def validators_json():
    """Public, read-only: lets nodes display validator status (e.g. on the
    Miner page) without needing the admin key."""
    return jsonify({"validators": store.list_validators()})


def _admin_key_ok(supplied: str) -> bool:
    return bool(supplied) and hmac.compare_digest(supplied, config.MCA_ADMIN_KEY)


@app.route("/admin/validators", methods=["GET", "POST"])
def admin_validators():
    error = None
    success = None
    if request.method == "POST":
        admin_key = request.form.get("admin_key", "")
        action = request.form.get("action")
        address = request.form.get("address", "").strip()
        label = request.form.get("label", "").strip()

        if not _admin_key_ok(admin_key):
            error = "Incorrect admin key."
        elif not address:
            error = "An address is required."
        elif action == "add":
            store.add_validator(address, label)
            success = f"Approved {address[:16]}... as a validator."
        elif action == "remove":
            if store.remove_validator(address):
                success = f"Revoked validator status for {address[:16]}..."
            else:
                error = "That address wasn't on the validator list."
        else:
            error = "Unknown action."

    return render_template(
        "mca_admin.html",
        validators=store.list_validators(), error=error, success=success,
    )


@app.route("/")
def dashboard():
    certs = store.all_certificates()[:100]
    now = time.time()
    return render_template(
        "mca_dashboard.html", certs=certs, now=now, port=PORT,
        validator_count=len(store.list_validators()),
        public_key=store.get_public_key(),
    )


if __name__ == "__main__":
    print(f"[MCA] Mining Certificate Authority listening on 0.0.0.0:{PORT}")
    print(f"[MCA] Data file: {store.path}")
    print(f"[MCA] Public key (safe to share with every node): {store.get_public_key()}")
    app.run(host="0.0.0.0", port=PORT, threaded=True)
