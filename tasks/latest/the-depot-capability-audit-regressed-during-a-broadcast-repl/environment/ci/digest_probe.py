"""Digest helpers mirroring kel_contract ticket bind and audit fold rules."""

from __future__ import annotations

import hashlib
import hmac

MAC_KEY = b"depot-capability-v1-key-material-32b!!"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ticket_mac(principal: str, ticket_id: str, parent_id: str, epoch: int, scope: int) -> str:
    msg = f"{principal}|{ticket_id}|{parent_id}|{epoch}|{scope}".encode()
    return hmac.new(MAC_KEY, msg, hashlib.sha256).hexdigest()
