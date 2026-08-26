# Sample Windows

The `.ase` files store short sampled signal windows from one instrument in a
compact binary format.

All integer fields are unsigned unless noted. Mixed byte order is part of the
format and is fixed by field:

| Field | Type | Byte order |
|---|---:|---|
| magic `ASE1` | 4 bytes | raw |
| version | uint8 | raw |
| instrument_id | uint32 | big endian |
| window_count | uint16 | little endian |
| reserved | uint16 | little endian |

Each window then contains:

| Field | Type | Byte order |
|---|---:|---|
| window_id | uint32 | big endian |
| start_tick | uint64 | little endian |
| nominal_dt_ns | float64 | little endian |
| sample_count | uint16 | big endian |
| present_count | uint16 | big endian |
| scale | float32 | little endian |
| offset | float32 | little endian |
| present_mask | ceil(sample_count / 8) bytes | low bit first |
| present samples | int16[present_count] | big endian |

The sample at logical index `i` has raw time
`start_tick * 1e-9 + i * nominal_dt_ns * 1e-9` before instrument clock
calibration. Only indices whose mask bit is set have a stored sample. Physical
sample value is `scale * raw_sample + offset`.
