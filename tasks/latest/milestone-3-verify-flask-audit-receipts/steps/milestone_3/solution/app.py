"""Flask transparency-log API for Ed25519-signed release manifests.

Endpoints:
  POST /manifests          upload a manifest, returns its canonical hash
  POST /signatures         submit {manifest, signature, public_key_pem};
                           verifies the Ed25519 signature over the canonical
                           hash, appends to the append-only log, returns receipt
  GET  /receipts/<index>   retrieve the receipt for a log index
  GET  /audit              inspect the full append-only audit log + chain status

Rejections:
  - invalid Ed25519 signature              -> 400
  - manifest_hash mismatch (tampered)      -> 400
  - replayed (manifest, signature)         -> 409
"""

import base64

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from flask import Flask, jsonify, request

from canonical import canonical_hash
from log import TransparencyLog


def create_app(log_path: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config["LOG"] = TransparencyLog(log_path)

    @app.post("/manifests")
    def upload_manifest():
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or "manifest" not in body:
            return jsonify({"error": "missing manifest"}), 400
        return jsonify({"manifest_hash": canonical_hash(body["manifest"])}), 200

    @app.post("/signatures")
    def submit_signature():
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"error": "invalid body"}), 400
        for field in ("manifest", "signature", "public_key_pem"):
            if field not in body:
                return jsonify({"error": f"missing {field}"}), 400

        manifest_hash = canonical_hash(body["manifest"])

        # Optional client-asserted hash must match the server's computation.
        if "manifest_hash" in body and body["manifest_hash"] != manifest_hash:
            return jsonify({"error": "manifest_hash mismatch (tampered manifest)"}), 400

        try:
            pub = serialization.load_pem_public_key(body["public_key_pem"].encode())
            if not isinstance(pub, Ed25519PublicKey):
                raise ValueError("not Ed25519")
            pub.verify(base64.b64decode(body["signature"]), manifest_hash.encode("ascii"))
        except (InvalidSignature, ValueError, Exception):
            return jsonify({"error": "invalid signature"}), 400

        try:
            entry = app.config["LOG"].append(manifest_hash, body["signature"])
        except KeyError:
            return jsonify({"error": "replayed receipt"}), 409

        return jsonify({"receipt": entry}), 200

    @app.get("/receipts/<int:index>")
    def get_receipt(index: int):
        entries = app.config["LOG"].entries()
        if index < 0 or index >= len(entries):
            return jsonify({"error": "no such receipt"}), 404
        return jsonify({"receipt": entries[index]}), 200

    @app.get("/audit")
    def audit():
        log = app.config["LOG"]
        return jsonify({"entries": log.entries(), "chain_valid": log.verify_chain()}), 200

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000)
