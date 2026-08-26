# SMP-7 — Spectral Methods Procedure, Revision D

Adopted 2025-03-12 by resolution recorded in minute DRB-2025-03. Supersedes
the interim arrangement in effect since erratum E-2024-04.

## §1 Purpose

Defines the estimation method the spectral service must implement when it
reports band-integrated power for a telemetry channel over a capture window.

## §2 Frame selection

A request names a channel and a half-open capture window `[from, to)`. The
method operates on every stored frame of that channel whose `captured_at`
falls in the window, ordered by capture time. Band powers are computed per
frame and combined across frames by arithmetic mean.

## §3 Segmentation

Each frame is divided into analysis segments of exactly 1024 samples. The
segment start advances by 512 samples between consecutive segments, so that
adjacent segments overlap by half their length. Segments that would extend
past the end of the frame are not taken.

## §4 Detrending and windowing

Before windowing, the arithmetic mean of the segment's samples is subtracted
from every sample of that segment. The segment is then multiplied by the
symmetric Hann window

    w[i] = 0.5 * (1 - cos(2 * pi * i / (L - 1))),   i = 0 .. L-1,

where L is the segment length. Revision C's periodic form (denominator L) is
not to be used; the symmetric form restores the tapering behaviour that
revisions A and B relied on.

## §5 Periodogram scaling

For each windowed segment, take the discrete Fourier transform and form the
one-sided density estimate over bins k = 0 .. L/2:

    P[k] = 2 * |X[k]|^2 / (fs * S),

where fs is the sample rate and S is the sum of the squared window samples,
S = sum over i of w[i]^2. The factor 2 accounts for the discarded negative
frequencies and is therefore omitted at k = 0 and k = L/2, where no mirror
bin exists: at those two bins the density is |X[k]|^2 / (fs * S). Segment
estimates are averaged bin-wise across all segments of the frame.

## §6 Band assignment and integration

The frequency of bin k is f_k = k * fs / L, taken exactly; the nearest-tenth
rounding rule of revision C is abolished. A bin belongs to a band when
`lower <= f_k < upper` — intervals are half-open, closed at the lower bound
and open at the upper. Band power is the sum of P[k] * (fs / L) over the
band's bins.

## §7 Reporting bands

Five bands are defined:

| band | lower (Hz) | upper (Hz) |
|---|---|---|
| quiet | 0.5 | 8 |
| pulse_low | 8 | 24 |
| pulse_mid | 24 | 64 |
| pulse_high | 64 | 128 |
| burst | 128 | 224 |

The guard band that revision C carried above 224 Hz is not reported under
this revision. The burst upper bound moves from the 192 Hz of revision B to
224 Hz, following the 2024–2025 burst-event reanalysis. Energy at or above
224 Hz is not reported by any band.

## §8 Reporting

The service response states the revision letter of the procedure in force.
Band rows are reported in ascending order of lower bound.
