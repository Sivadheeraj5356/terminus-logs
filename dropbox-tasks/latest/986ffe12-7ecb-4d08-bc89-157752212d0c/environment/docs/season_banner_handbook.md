# Season 9 Stellarbloom banner handbook

Live ops validates committed gacha sessions before prize desk payouts.

MAC domain labels in config are cosmetic — HMAC always uses the raw `hmac_key` bytes. Draw rolls stay session-first with one-based indices and host-endian digest words. Item pools rank reverse-lexicographic. Receipts keep rarity-before-item order. Seed commits prefer hex-decoded provisioning bytes.

Pity is player-scoped. Soft-floor to uncommon when pity is strictly past threshold-1. Pity gap resets only when sessions are closer than the configured gap (dense play protection). Live overlay and desk_fallback own weekend HMAC, pity, gap, and domain labels.

Duplicate session ids keep the latest `opened_at` (revision is informational). Colliding pulls keep the newest occurrence. Digests reverse receipt order. Seed failures still advance pity so streaks survive bad commits. Integrity uses tainted coverage. Rows sort by player id. Ledger keys collapse to player-only.
