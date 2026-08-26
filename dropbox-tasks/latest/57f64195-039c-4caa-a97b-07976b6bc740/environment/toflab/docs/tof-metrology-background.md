# TOF cubic mass-axis background

This document describes the scientific mass metrology criterion used by the bench.
Reflectron and linear TOF analyzers map ion arrival time into mass-to-charge with a
nearly quadratic flight law. Higher-order field imperfections are commonly absorbed
into a small cubic residual:

```
m/z = k (t - t0)^2 + q (t - t0)^3
```

`k` absorbs effective path length and acceleration potential, `t0` absorbs
trigger/cable delay, and `q` absorbs weak cubic residuals from reflectron voltage
ripple. Modern bench transfers report the full coefficient vector with pairwise
correlations, so cross-bench fusion is a numerical scientific-computing problem:
convert milli-Dalton and nanosecond transcriptions through a joint covariance
transform, test physical monotonicity of the cubic axis over the measured flight
interval, and fuse admissible candidates with robust generalized least squares
before propagating full parameter uncertainty into corrected-mass residuals and
catalog ion assignment. Platform telemetry with substantially tighter generalized
uncertainty than surviving bench candidates may lock; otherwise the GLS merge is
used.
