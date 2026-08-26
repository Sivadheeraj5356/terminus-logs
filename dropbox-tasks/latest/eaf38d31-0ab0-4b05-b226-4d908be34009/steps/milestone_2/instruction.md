Milestone 2 — Sign with Ed25519 Keys

Now that manifests can be canonicalized and hashed, add local Ed25519 signing key management and manifest signing to the CLI.

Implement the key/signature logic in a flat module at exactly /app/transparency/keys.py and extend /app/transparency/cli.py to support these invocations: python3 /app/transparency/cli.py keygen --key-dir /app/keys; python3 /app/transparency/cli.py sign <manifest.json> --key-dir /app/keys --out /app/out; and python3 /app/transparency/cli.py verify <manifest.json> --key-dir /app/keys --sig /app/out/manifest.sig.

The keygen subcommand generates an Ed25519 keypair and writes PEM files ed25519_private.pem (PKCS8, unencrypted) and ed25519_public.pem (SubjectPublicKeyInfo) into the key directory.

The sign subcommand computes the canonical SHA-256 digest of the manifest (milestone 1) and signs it with the private key. The signed message is the ASCII bytes of the lowercase 64-character hex digest string (that is, digest_hex.encode("ascii")) — not the raw 32 digest bytes. Write the base64-encoded signature to <out>/manifest.sig.

The verify subcommand recomputes the digest and prints exactly the word valid (and exits 0) when the signature matches, or prints exactly the word invalid (and exits non-zero) when it does not. A manifest that has been altered in any way must print invalid.

Demonstrate by generating a keypair under /app/keys, signing /app/data/manifest.json into /app/out/manifest.sig, and verifying it.
