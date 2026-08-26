# Multi-rate sample folding

Candidate `omega` and capture `sample_rate` are positive JSON integers. Let
`m = omega mod sample_rate`, with `0 <= m < sample_rate`.

- If `m > floor(sample_rate / 2)`, the folded bin is `sample_rate - m` and the
  sampled sine coordinate is negated.
- Otherwise, the folded bin is `m` and the sampled sine coordinate keeps its sign.
- At bin zero, and at bin `sample_rate / 2` when the sample rate is even, sampled
  sine is identically zero. The sine sign reported for these collapsed bins is `0`;
  for the two ordinary cases it is `-1` and `1`, respectively.

Cosine never changes sign merely because of folding. Trigger rotation and the calibrated
path response occur before the folding rule. A source contribution is added only to its
folded bin for that capture and probe.

Several analog lines may fold onto the same bin and their exact coordinates add. The
same analog line generally follows a different bin track across captures. Recovery must
honour all collisions and all zero-residual bins; assigning each measured bin to one
low-frequency source independently is not equivalent to the campaign model.

Every capture file has:

- `capture_id`, `sample_rate`, and `trigger_quarters`;
- one `probes` row for every campaign probe;
- every integer bin from zero through `floor(sample_rate / 2)` exactly once;
- `expected.cos`, `expected.sin`, `measured.cos`, and `measured.sin` reduced fractions.

Rows and files may appear in any order. Their canonical order is defined by the product
contract, not by their input position.
