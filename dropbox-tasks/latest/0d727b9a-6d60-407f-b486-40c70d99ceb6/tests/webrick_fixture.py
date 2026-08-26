"""Shared helpers for the flat ruby-webrick-escape-room-hardening verifier."""
import hashlib
import hmac
import json
import os
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.request
import uuid

import yaml

SETTINGS_PATH = "/app/config/settings.yaml"


def find_free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_server(port, rate_limit_rpm=None):
    env = os.environ.copy()
    env["PORT"] = str(port)
    env["BIND_ADDR"] = "127.0.0.1"
    with open(SETTINGS_PATH, "r") as f:
        cfg = yaml.safe_load(f)
    cfg["port"] = port
    with open(SETTINGS_PATH, "w") as f:
        yaml.safe_dump(cfg, f)
    if rate_limit_rpm is not None:
        env["RATE_LIMIT_RPM"] = str(rate_limit_rpm)
    env["RUBYOPT"] = "-rbundler/setup"
    proc = subprocess.Popen(
        ["ruby", "/app/server.rb"],
        cwd="/app",
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"{base}/health", timeout=1)
            return proc, base
        except Exception:
            time.sleep(0.3)
    proc.kill()
    raise RuntimeError("server did not become healthy in time")


def stop_server(proc):
    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def get_admin_secret():
    with open(SETTINGS_PATH) as f:
        return yaml.safe_load(f).get("admin_secret", "")


def get_moderator_key():
    with open(SETTINGS_PATH) as f:
        return yaml.safe_load(f).get("moderator_key", "")


def signed_admin_headers(path, secret, ts_offset=0, nonce=None):
    """Build correct X-Timestamp, X-Nonce, X-Admin-Signature headers per API spec."""
    ts = int(time.time()) + ts_offset
    n = nonce or str(uuid.uuid4())
    msg = f"{path}:{ts}:{n}".encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    return {"X-Timestamp": str(ts), "X-Nonce": n, "X-Admin-Signature": sig}


def http_post(url, body=None, headers=None, raw_data=None):
    if raw_data is not None:
        data = raw_data
    else:
        data = json.dumps(body or {}).encode()
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            raw = r.read()
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = {}
            return r.status, parsed
    except urllib.error.HTTPError as e:
        raw = e.read() or b"{}"
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {}
        return e.code, parsed


def http_get(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def new_session(base):
    """Create a new game session and return the session_id."""
    data = b"{}"
    req = urllib.request.Request(
        f"{base}/session/new",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read())["session_id"]
