# Module scope (behavior packages)

Offline FlashAttention / KV-cache inference-evaluation packages:

- **Tile scheduling** — Br/Bc sizing, visitation order, K-tile page allocation requests
- **Online softmax ring** — running m/ℓ with α rescale
- **Block table pager** — logical↔physical map, LIFO free list, compact gate
- **Sparse mask gate** — packed bit rehydration in stored index order
- **Quant tile codec** — int8 dequant for local tile stats
- **Residency ledger** — KVT1 binary persistence across runs
- **Seal ring** — canonical JSON + SHA-256 digest
- **Merkle spine** — parent-chained tip across advance epochs
- **Seal trailer** — tip XOR profile salt gate on replan

Cross-package cascade: tile scheduling mutations of the pager are the only source of truth for which physical pages the seal ring may hash.
