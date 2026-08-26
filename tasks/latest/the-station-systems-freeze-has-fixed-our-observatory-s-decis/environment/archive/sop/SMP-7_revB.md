# SMP-7 — Spectral Methods Procedure, Revision B

Adopted 2021-07-22 by resolution recorded in minute DRB-2021-08. Supersedes
revision A. Following erratum E-2024-04's rescission of revision C, this
revision returned to force on an interim basis under SOP-9 §4 until the
adoption of revision D on 2025-03-12.

## §1 Purpose

Defines the estimation method for band-integrated power reporting. Revision B
introduced overlapped segmentation and window-energy scaling to the station.

## §2 Frame selection

Frames of the named channel with `captured_at` in the half-open window
`[from, to)`; band powers averaged arithmetically across frames.

## §3 Segmentation

Segments of 1024 samples, advancing 512 samples between consecutive segments
(half overlap). Segments extending past the end of the frame are not taken.

## §4 Detrending and windowing

The arithmetic mean of each segment is subtracted before windowing. Each
segment is multiplied by the symmetric Hann window

    w[i] = 0.5 * (1 - cos(2 * pi * i / (L - 1))),   i = 0 .. L-1.

## §5 Periodogram scaling

One-sided estimate over bins k = 0 .. L/2:

    P[k] = 2 * |X[k]|^2 / (fs * S),   S = sum over i of w[i]^2,

halved at k = 0 and k = L/2, averaged bin-wise across segments.

## §6 Band assignment and integration

Bin frequencies f_k = k * fs / L are taken exactly. A bin belongs to a band
when `lower <= f_k < upper` (half-open). Band power is the sum of
P[k] * (fs / L) over the band's bins.

## §7 Reporting bands

Five bands are defined:

| band | lower (Hz) | upper (Hz) |
|---|---|---|
| quiet | 0.5 | 8 |
| pulse_low | 8 | 24 |
| pulse_mid | 24 | 64 |
| pulse_high | 64 | 128 |
| burst | 128 | 192 |

Energy above 192 Hz is not reported by any band under this revision.

## §8 Reporting

The service response states the revision letter of the procedure in force.
