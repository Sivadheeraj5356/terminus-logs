#!/usr/bin/env python3

from flask import Flask, jsonify

app = Flask(__name__)

MODELS = {
    "fraud_guard_prod": {"approved": True, "owner": "risk-platform"},
    "ranking_shadow": {"approved": False, "owner": "search-experimental"},
}


@app.get("/v1/models/<model_id>/deployment")
def deployment_status(model_id: str):
    record = MODELS.get(model_id)
    if record is None:
        return jsonify({"error": "model not found", "model_id": model_id}), 404
    return jsonify(
        {
            "model_id": model_id,
            "approved": record["approved"],
            "deployment_approved": True,
            "owner": record["owner"],
        }
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080)
