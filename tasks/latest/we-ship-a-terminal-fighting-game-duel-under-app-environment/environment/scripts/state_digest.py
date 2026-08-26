#!/usr/bin/env python3
"""SHA-256 trajectory digest over six-byte duel states (see duel_rules.md)."""

import argparse
import hashlib
import json
import sys


def trajectory_digest(states):
    buf = bytearray()
    for row in states:
        buf += bytes(int(x) & 0xFF for x in row)
    return hashlib.sha256(bytes(buf)).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--states-file")
    args = parser.parse_args()
    raw = open(args.states_file).read() if args.states_file else sys.stdin.read()
    print(trajectory_digest(json.loads(raw)))


if __name__ == "__main__":
    main()
