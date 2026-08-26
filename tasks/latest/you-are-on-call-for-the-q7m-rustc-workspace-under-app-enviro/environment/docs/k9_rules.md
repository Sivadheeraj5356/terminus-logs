# k9 rules — position identity and trace contract

## Position identity (reference contract)

Treat this document — not any external FIDE text — as the contract. The rules
follow FIDE threefold repetition in spirit, but the position key uses this
implementation's own square encoding described below. Two positions are equal
only when every item below matches.

1. Side to move (white or black)
2. Piece placement on all 64 squares
3. Castle permission bits (K Q k q — each may be present or absent)
4. For the en-passant component, when a pawn has just advanced two ranks, record
   the square the moved pawn left (its origin square) — not the FIDE capture-target
   square behind it; otherwise none.

## Outcome code alphabet

| Code | Meaning |
|------|---------|
| `N` | No draw claim on this ply |
| `H` | Half-move draw claim (third occurrence of the same legal position) |

## Repetition occurrence counting

Track how many times each legal position key has appeared within the current segment. The key uses the four equality components above (placement, side, castling bits, ep square).

Before incrementing the count for the position after a move, check whether that move was irreversible. If it was, clear the occurrence counter and start a new segment.

Irreversible moves are captures, pawn moves of any distance, and king moves from the e-file to the g-file or c-file (castling under UCI).

Castling appears in the fixtures as a single UCI king move such as `e1g1` or
`e1c1`. The reference relocates only the king for these moves; it does not move
the rook, so placement reflects only the king's new square.

Emit `H` when the same position key would reach its third occurrence in the current segment; otherwise emit `N`.

## Position digest (`digest_hex`)

Each trace row carries a 64-bit digest of the position after the move, written as 16 lowercase hexadecimal characters.

Compute the digest from the post-move position as follows.

The 64 placement bytes are the engine board grid cell values in square order a1
through h8: occupied squares use the grid's ASCII piece letter; empty squares use
ASCII space (0x20).

1. FNV-1a over the 64 placement bytes with initial value `0xcbf29ce484222325`; for each byte, XOR it in, then multiply by `0x100000001b3` with 64-bit wrap.
2. XOR `0x01` when white is to move, otherwise XOR `0x02`.
3. XOR the castling-permission mask into bits 8..15 (mask bit 0 is K, 1 is Q, 2 is k, 3 is q).
4. When a pawn has just advanced two ranks, XOR `((origin_square + 1) << 16)`,
   where `origin_square` is the 0..63 index of the square the pawn left (the
   en-passant component from the identity list above).

The digest identifies position identity for matching; it does not include the segment occurrence counter.

## Trace row schema (`event_trace.jsonl`)

One JSON object per line, one line per ply after each scripted move.

| Field | Type | Requirement |
|------|------|-------------|
| ply | integer | 1-based ply index |
| digest_hex | string | exactly 16 lowercase hexadecimal characters per digest section above |
| outcome_code | string | `N` or `H` per table above |

## Mismatch report schema (`m1_mismatch_report.json`)

Top-level object with three keys.

| Key | Type | Requirement |
|-----|------|-------------|
| schema | string | must be `k9-mismatch-v1` |
| fixtures | array of strings | fixture basenames included in the report |
| mismatches | array of objects | each object uses the four field names in the example below |

Example mismatch object with these exact JSON keys

```json
{"fixture": "seq_r4.pgn", "ply": 16, "engine": "H", "reference": "N"}
```

| Field | Meaning |
|-------|---------|
| fixture | basename of the fixture script |
| ply | 1-based ply index where the engine diverged |
| engine | outcome code produced by the engine |
| reference | outcome code produced by the bundled reference |

Milestone 1 compares `/app/environment/fixtures/seq_r4.pgn` and `/app/environment/fixtures/seq_u8.pgn` only.

## Fixture move format

Fixtures list one UCI move per non-empty line (e.g. `e2e4`). Lines starting with `#` are comments.

Bundled fixtures under `/app/environment/fixtures/` must remain unmodified. Integrity checks compare each fixture file against a pinned full-file `sha256` value (lowercase hexadecimal). During the observation stage the Rust workspace sources and manifests under `/app/environment` are integrity-pinned the same way, file by file; they become editable once the repair stages begin.

## CLI usage

Build or rebuild with `bash /app/environment/scripts/build_q7m.sh`, then run the engine with `run-seq`, a fixture path via `--script`, and optional `--out` for the JSONL destination.

Default trace filename is `event_trace.jsonl` in the container output workspace when `--out` is omitted.

This is a standard Cargo workspace whose manifest is `/app/environment/Cargo.toml`. The build script wraps `cargo build --release`; the same binary can be produced directly with `cargo build --release --offline --manifest-path /app/environment/Cargo.toml`, and `--target-dir <dir>` sends the compiled artifacts to a chosen directory. The grader compiles the workspace this way from the sources under `/app/environment` and runs the binary it builds itself, so any correction must live in the Rust modules — a hand-edited trace, a pre-placed binary, or a doctored build script does not count.

## Output artifact policy

Hand-written or manually edited trace and report files are insufficient, artifacts must be produced by rebuilding the engine and running the normal `run-seq` pipeline.

Library and module behavior under `/app/environment` must be correct, repairing only the CLI wrapper without fixing underlying engine modules is insufficient.
