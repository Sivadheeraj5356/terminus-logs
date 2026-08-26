# SMP-7 — Spectral Methods Procedure, Revision A

Adopted 2019-03-14 by resolution recorded in minute DRB-2019-04. The
station's first written spectral procedure. Superseded by revision B on
2021-07-22.

## §1 Purpose

Defines the original band-power reporting method used during station
commissioning.

## §2 Method

Each stored frame is analysed whole, without segmentation: a single
periodogram is taken over the full 8192-sample frame after multiplying by a
symmetric Hann window computed with denominator L - 1. The one-sided
estimate is scaled by 2 / (fs * S) with S the sum of squared window samples,
halved at the zero and Nyquist bins. No detrending is performed.

## §3 Reporting bands

Four bands are defined, assigned on exact bin frequencies with half-open
intervals:

| band | lower (Hz) | upper (Hz) |
|---|---|---|
| quiet | 0.5 | 10 |
| pulse | 10 | 60 |
| storm | 60 | 150 |
| burst | 150 | 256 |

## §4 Notes

Commissioning experience showed the whole-frame periodogram too variable for
routine reporting; revision B replaced it with averaged overlapping segments.
