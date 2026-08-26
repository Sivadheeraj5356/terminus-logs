# Key URI containment

Sealed artifacts must never embed http:// or https:// key locations.

Allowed key reference forms:

- key_id opaque token from the Gin API
- key_urn of the form urn:reelseal:key:<key_id>

Legacy YAML/TOML under /app/legacy intentionally contain http key URIs for decoy testing. The sealing pipeline must not copy those strings into /app/output or /app/state/hls/index.m3u8.
