#!/usr/bin/env python3
"""Transparency CLI: canonicalize, sign, and verify release manifests.

Milestone 1 implements `canonicalize`. Later milestones add `keygen`, `sign`,
and `verify`, which lazily import their dependencies so this CLI works as each
milestone's modules appear in /app/transparency/.
"""

import argparse
import sys
from pathlib import Path

from canonical import canonical_hash, canonicalize, load_manifest


def cmd_canonicalize(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    canon = canonicalize(manifest)
    digest = canonical_hash(manifest)
    (out_dir / "manifest.canonical.json").write_bytes(canon)
    (out_dir / "manifest.sha256").write_text(digest + "\n")
    print(digest)
    return 0


def cmd_keygen(args: argparse.Namespace) -> int:
    from keys import generate_keypair

    priv, pub = generate_keypair(args.key_dir)
    print(f"private={priv}")
    print(f"public={pub}")
    return 0


def cmd_sign(args: argparse.Namespace) -> int:
    from keys import sign_digest

    manifest = load_manifest(args.manifest)
    digest = canonical_hash(manifest)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    sig = sign_digest(str(Path(args.key_dir) / "ed25519_private.pem"), digest)
    (out_dir / "manifest.sig").write_text(sig + "\n")
    print(sig)
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    from keys import verify_digest

    manifest = load_manifest(args.manifest)
    digest = canonical_hash(manifest)
    sig = Path(args.sig).read_text().strip()
    ok = verify_digest(str(Path(args.key_dir) / "ed25519_public.pem"), digest, sig)
    print("valid" if ok else "invalid")
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Release manifest transparency CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("canonicalize")
    p.add_argument("manifest")
    p.add_argument("--out", default="/app/out")
    p.set_defaults(func=cmd_canonicalize)

    p = sub.add_parser("keygen")
    p.add_argument("--key-dir", default="/app/keys")
    p.set_defaults(func=cmd_keygen)

    p = sub.add_parser("sign")
    p.add_argument("manifest")
    p.add_argument("--key-dir", default="/app/keys")
    p.add_argument("--out", default="/app/out")
    p.set_defaults(func=cmd_sign)

    p = sub.add_parser("verify")
    p.add_argument("manifest")
    p.add_argument("--key-dir", default="/app/keys")
    p.add_argument("--sig", default="/app/out/manifest.sig")
    p.set_defaults(func=cmd_verify)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
