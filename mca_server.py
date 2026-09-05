"""
Mining Certificate Authority (MCA) server.

Run one of these per network (it's the "central" service that must be
running in the background). Miners request a certificate from it before
mining each block, and nodes double-check every submitted block's
certificate against this service's database before accepting the block.

Run:
    python mca_server.py
Env vars:
    MCA_PORT   (default 6000)
    MCA_SECRET_KEY  must match the value every node in the network uses (see config.py)
"""
import os
import time

from flask import Flask, jsonify, request, render_template

from mca_store import MCAStore

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

PORT = int(os.environ.get("MCA_PORT", 6000))
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


@app.route("/request_certificate", methods=["POST"])
def request_certificate():
    body = request.get_json(force=True, silent=True) or {}
    miner_address = body.get("miner_address")
    block_index = body.get("block_index")
    prev_hash = body.get("prev_hash")

    if not miner_address or block_index is None or not prev_hash:
        return jsonify({"error": "miner_address, block_index and prev_hash are required"}), 400

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


@app.route("/")
def dashboard():
    certs = store.all_certificates()[:100]
    now = time.time()
    return render_template("mca_dashboard.html", certs=certs, now=now, port=PORT)


if __name__ == "__main__":
    print(f"[MCA] Mining Certificate Authority listening on 0.0.0.0:{PORT}")
    print(f"[MCA] Data file: {store.path}")
    app.run(host="0.0.0.0", port=PORT, threaded=True)
