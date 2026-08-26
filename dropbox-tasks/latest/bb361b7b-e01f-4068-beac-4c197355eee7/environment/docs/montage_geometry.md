# Montage geometry

Each capture is a horizontally packed grayscale montage of fixed size cells. Cell width,
height, and sampling interval are recorded in `environment/capture_constants/capture_geometry.json`.

The solver must treat the montage as a time series of bob images rather than as a tabular export.
