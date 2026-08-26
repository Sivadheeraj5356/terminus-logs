#!/usr/bin/env python3
import hashlib
import sys

def sha256_hex(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()

def main() -> None:
    if len(sys.argv) < 2:
        print("usage: parity_sha.py hex <line>|file -", file=sys.stderr)
        sys.exit(2)
    mode = sys.argv[1]
    if mode == "hex":
        print(sha256_hex(sys.argv[2]))
    elif mode == "file":
        data = sys.stdin.buffer.read()
        print(sha256_hex(data))
    else:
        sys.exit(2)

if __name__ == "__main__":
    main()
