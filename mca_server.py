"""
Mining Certificate Authority (MCA) server - under PoA, this is the
network's validator registry and governance point. Run one of these per
network; it must stay running for the current validator rotation to be
knowable, but unlike the network's earlier design it is never involved
in producing or checking any individual block.

Run:
    python mca_server.py
Env vars:
    MCA_PORT       (default 6060)
    MCA_ADMIN_KEY  required to manage the validator whitelist at /admin/validators
                   (see config.py - do not distribute this to node operators)
"""
import hmac
import os

from flask import Flask, jsonify, request, render_template

import config
import poa
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
        "service": "Mining Certificate Authority (validator registry)",
        "status": "online",
        "port": PORT,
        "validator_count": len(store.list_validators()),
    })


@app.route("/validators")
def validators_json():
    """Public, read-only, no auth needed: lets every node learn the
    current, authoritative rotation order. This is not sensitive
    information - it has to be public for PoA to work at all."""
    return jsonify({"validators": store.list_validators(), "order": store.ordered_addresses()})


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

    order = store.ordered_addresses()
    return render_template(
        "mca_admin.html",
        validators=store.list_validators(), order=order, error=error, success=success,
    )


@app.route("/")
def dashboard():
    order = store.ordered_addresses()
    # Show who'd be expected to propose the next several block indices,
    # purely as a friendly display of the rotation - no block state lives here.
    upcoming = [(i, poa.primary_proposer(order, i)) for i in range(1, 6)] if order else []
    return render_template(
        "mca_dashboard.html", port=PORT,
        validators=store.list_validators(), order=order, upcoming=upcoming,
    )


if __name__ == "__main__":
    print(f"[MCA] Validator registry listening on 0.0.0.0:{PORT}")
    print(f"[MCA] Data file: {store.path}")
    app.run(host="0.0.0.0", port=PORT, threaded=True)
