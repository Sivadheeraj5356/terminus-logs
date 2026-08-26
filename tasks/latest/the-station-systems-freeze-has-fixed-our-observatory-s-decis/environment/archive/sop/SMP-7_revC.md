# SMP-7 — Spectral Methods Procedure, Revision C

Adopted 2023-05-09 by resolution recorded in minute DRB-2023-11. Supersedes
revision B. Status note appended 2024-05-16: this revision was rescinded in
its entirety by erratum E-2024-04 and must not be applied to new work. The
text is retained for the historical record.

## §1 Purpose

Defines the estimation method for band-integrated power reporting, revised
from B to reduce computation on the station's then-limited processing budget.

## §2 Frame selection

As revision B: frames of the named channel with `captured_at` in the
half-open window `[from, to)`, band powers averaged arithmetically across
frames.

## §3 Segmentation

Segments of 1024 samples. To reduce segment count, the segment start advances
by three quarters of the segment length (768 samples) between consecutive
segments, giving one-quarter overlap. Segments extending past the end of the
frame are not taken.

## §4 Windowing

No detrending step is performed; the station's fluxgate channels were judged
sufficiently zero-centred. Each segment is multiplied by the periodic Hann
window

    w[i] = 0.5 * (1 - cos(2 * pi * i / L)),   i = 0 .. L-1,

with L the segment length.

## §5 Periodogram scaling

One-sided estimate over bins k = 0 .. L/2:

    P[k] = 2 * |X[k]|^2 / (fs * L),

halved at k = 0 and k = L/2. The window-energy denominator of revision B was
replaced by the plain segment length for computational economy.

## §6 Band assignment and integration

The frequency of bin k, f_k = k * fs / L, is rounded to the nearest tenth of
a hertz before comparison. A bin belongs to a band when
`lower <= f_rounded <= upper` — intervals are closed at both bounds. Band
power is the sum of P[k] * (fs / L) over the band's bins.

## §7 Reporting bands

Six bands are defined:

| band | lower (Hz) | upper (Hz) |
|---|---|---|
| quiet | 0.5 | 8 |
| pulse_low | 8 | 24 |
| pulse_mid | 24 | 64 |
| pulse_high | 64 | 128 |
| burst | 128 | 224 |
| guard | 224 | 256 |

The guard band was added to watch anti-aliasing margin on the 512 Hz
channels.

## §8 Reporting

The service response states the revision letter of the procedure in force.
