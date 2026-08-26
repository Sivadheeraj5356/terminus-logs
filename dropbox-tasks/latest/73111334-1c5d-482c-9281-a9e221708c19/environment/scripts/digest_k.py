#!/usr/bin/env python3
import hashlib
import sys

data = sys.stdin.buffer.read()
print(hashlib.sha256(data).hexdigest()[:16])
