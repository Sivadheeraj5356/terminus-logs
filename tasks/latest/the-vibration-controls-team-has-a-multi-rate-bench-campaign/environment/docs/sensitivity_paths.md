# Calibrated sensitivity paths

Each file under `/app/plant_lab/paths/` identifies one `source_id`, one `probe_id`,
and two coefficient arrays, `numerator` and `denominator`. Array position is polynomial
degree: entry zero is the constant coefficient, entry one multiplies `s`, and so on.
Every coefficient is a reduced-fraction object.

For tone rate `omega`, the path value is

`H(j omega) = numerator(j omega) / denominator(j omega)`.

Polynomial evaluation and complex division use exact rational real and imaginary
components. A zero denominator at any candidate rate makes the campaign invalid. Leading
zero coefficients are permitted and remain part of the input, although they do not
change the value.

The path set is complete: there is exactly one file for every source named by
`campaign.json` crossed with every named probe, and no path may name an unknown source or
probe.

The visible bench includes the sensitivity

`s / (s^2 + s + 1)`

for the bearing-force to axis-tip path. This is one calibrated path among several; the
source reconstruction uses every probe path and every capture jointly. The path value
reported in `sensitivity_values` is the exact `(h_r, h_i)` pair at the selected tone's
analog rate, before trigger rotation and sample folding.
