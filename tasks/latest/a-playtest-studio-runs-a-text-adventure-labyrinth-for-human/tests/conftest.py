"""Shared fixtures: boot the real labyrinth-oracle binary once per test
session and hand every test an httpx client pointed at it.
"""

from __future__ import annotations

import socket
import subprocess
import time

import httpx
import pytest

BIN = "/app/bin/labyrinth-oracle"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_listening(proc: subprocess.Popen[str], needle: str, deadline: float) -> None:
    """Block until serve logs the listen line or the process exits."""
    assert proc.stdout is not None
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError("labyrinth-oracle exited before listening")
        line = proc.stdout.readline()
        if not line:
            time.sleep(0.02)
            continue
        if needle in line:
            return
    raise RuntimeError("labyrinth-oracle never logged listen address")


@pytest.fixture(scope="session")
def oracle_base_url():
    port = _free_port()
    addr = f"127.0.0.1:{port}"
    proc = subprocess.Popen(
        [BIN, "serve", "--addr", addr],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    base_url = f"http://{addr}"
    try:
        _wait_listening(proc, f"listening on {addr}", time.time() + 15)
        resp = httpx.get(f"{base_url}/health", timeout=2.0)
        if resp.status_code != 200:
            raise RuntimeError(f"health returned {resp.status_code}")
    except Exception:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        raise

    yield base_url

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture()
def client(oracle_base_url):
    with httpx.Client(base_url=oracle_base_url, timeout=5.0) as c:
        yield c


def create_session(
    client: httpx.Client,
    world_id: str | None = None,
    room_id: str | None = None,
    inventory: list[str] | None = None,
) -> dict:
    body: dict = {}
    if world_id is not None:
        body["world_id"] = world_id
    if room_id is not None:
        body["room_id"] = room_id
    if inventory is not None:
        body["inventory"] = inventory
    resp = client.post("/sessions", json=body)
    resp.raise_for_status()
    return resp.json()
