# Tracking contract

Accepted frames contribute angle samples to `recovered_series`. Rejected frames
are omitted from the time series but recorded in `recovery_edges` with
`kind = 'rejected'`. Per-job `fit_results.rejected_frames` must agree with the
rejected edge count for that job.
