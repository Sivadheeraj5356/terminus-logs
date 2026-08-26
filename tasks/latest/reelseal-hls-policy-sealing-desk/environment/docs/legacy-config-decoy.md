# Legacy config decoy

Files:

- /app/legacy/seal.yaml
- /app/legacy/seal.toml

These configs leak http key URIs such as http://keys.decoy.invalid/hls/aes.key and are non-authoritative. /app/decoy/legacy_seal_driver.go reads them for archival demos and must never be invoked by reelseal-desk.sh.
