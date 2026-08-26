import os
from pathlib import Path

import yaml
from flask import Flask, jsonify, request
from flask_cors import CORS
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "media.yaml"


def load_config():
    config_path = Path(os.environ.get("MEDIA_CONFIG", DEFAULT_CONFIG))
    with config_path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


CONFIG = load_config()
SERVICE = CONFIG.get("service", {})
MEDIA = CONFIG.get("media", {})

app = Flask(__name__)
app.config["DEBUG"] = bool(SERVICE.get("debug", True))
CORS(app, resources={r"/*": {"origins": SERVICE.get("cors_origins", ["*"])}})


@app.after_request
def add_headers(response):
    headers = SERVICE.get("response_headers", {})
    if headers.get("cache_control"):
        response.headers["Cache-Control"] = headers["cache_control"]
    if headers.get("x_content_type_options"):
        response.headers["X-Content-Type-Options"] = headers["x_content_type_options"]
    return response


def iter_media():
    fixture_dir = (ROOT / MEDIA.get("fixture_dir", "fixtures")).resolve()
    allowed = set(MEDIA.get("allowed_extensions", [".png", ".jpg", ".jpeg"]))
    items = []
    for file_path in sorted(fixture_dir.iterdir()):
        if file_path.suffix.lower() not in allowed:
            continue
        with Image.open(file_path) as image:
            item = {
                "name": file_path.name,
                "format": image.format,
                "width": image.width,
                "height": image.height,
                "mode": image.mode,
            }
        if MEDIA.get("include_absolute_paths", True):
            item["absolute_path"] = str(file_path)
        items.append(item)
    return items


@app.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "debug": app.debug,
        "cors_origins": SERVICE.get("cors_origins", ["*"]),
    })


@app.get("/media")
def media_index():
    return jsonify({
        "count": len(iter_media()),
        "items": iter_media(),
        "request_origin": request.headers.get("Origin", ""),
    })


if __name__ == "__main__":
    app.run(
        host=SERVICE.get("host", "0.0.0.0"),
        port=int(os.environ.get("PORT", SERVICE.get("port", 5055))),
        debug=bool(SERVICE.get("debug", True)),
    )
