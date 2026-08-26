# Window bucketing

Records bucket by `start_ms = (ts_ms / width_ms) * width_ms` using the profile-scoped width from cache or manifest.

Each window row reports `size_delta_sum`, `size_min`, `size_max`, and `seq_gap_sum`. Within-bucket gaps sum positive sequence holes between consecutive records sorted by `ts_ms`. Cross-bucket carry adds the gap between the first record in a bucket and the last sequence of the previous bucket when positive.
