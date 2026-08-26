# Run record schema

Each JSON file under `/app/output/runs/` carries these fields.

scenario_id is a string seat or resume label. seed is an integer. mode is the string flat or belt. final_counts is an object with integer dark and light filled-cell totals after the last accepted move. history_len is an integer count of accepted position digests retained. rejected_repeats is an integer count of moves refused for recreating a prior retained position. position_digests is an array of 64-character lowercase hex strings in acceptance order. terminal_digest is a 64-character lowercase hex string for the final grid.

## Product observations

Paired control seats that share the same seed and the same interior stone sequence should keep flat and belt records aligned on final_counts, history_len, rejected_repeats, position_digests, and terminal_digest. An immediate reverse capture that recreates a prior retained position should raise rejected_repeats and should not append another digest. A continued journal should finish with the same observation fields as an uninterrupted run of the same finished sequence. Repeating the same resume command should rewrite the same output path with identical JSON bytes. When a run accepts n moves and refused none, history_len and the digest array length should both be n. Digests stay 64-character lowercase hex. A journal whose saved prefix includes mid-prefix removals should keep history_len equal to the accepted placements that remain after fold.
