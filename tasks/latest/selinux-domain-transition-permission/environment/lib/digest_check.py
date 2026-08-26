#!/usr/bin/env python3
"""SHA-256 helper for verifier digest recomputation."""

import hashlib
import sys

data = sys.stdin.buffer.read()
sys.stdout.write(hashlib.sha256(data).hexdigest())
