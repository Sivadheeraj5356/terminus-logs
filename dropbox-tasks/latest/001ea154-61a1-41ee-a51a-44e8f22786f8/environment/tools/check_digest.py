#!/usr/bin/env python3
import hashlib
import sys

if __name__ == "__main__":
    print(hashlib.sha256(sys.argv[1].encode("utf-8")).hexdigest())
