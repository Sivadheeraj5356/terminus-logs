# Bob tracking notes

Each montage cell is a fixed width grayscale frame. A valid frame shows a dark bob on a light
background. Noised or occluded cells should be rejected before fitting. Accepted cells contribute
angle samples to `recovered_series` at the capture cadence documented in
`environment/capture_constants/capture_geometry.json`.
