# Radiometer contract

Normative band-integrated Planck radiometry and brightness-temperature inversion
for synthetic multi-band observations. Wavelengths in input files are micrometers;
all Planck formulas use wavelength in **meters**.

Companion inputs: `data_contract.md`. Companion thermal surface temperatures:
`thermal_model_contract.md`.

---

## Constants

Taken from `solver_config.json`:

- \(h =\) `planck_constant_j_s`
- \(c =\) `speed_of_light_m_s`
- \(k_B =\) `boltzmann_constant_j_k`

---

## Planck spectral radiance

\[
B_\lambda(\lambda, T)
=
\frac{2 h c^2}{
  \lambda^5 \bigl(\mathrm{e}^{h c / (\lambda k_B T)} - 1\bigr)
}
\]

Units: \(\mathrm{W\,m^{-2}\,sr^{-1}\,m^{-1}}\) (spectral radiance per meter of
wavelength).

Implementation requirements:

- Use a numerically stable exponential (for example `expm1` of the exponent).
- For nonpositive temperature or wavelength, treat radiance as zero.
- For extremely large exponents that underflow the exponential, treat radiance
  as zero.

---

## Band samples

For a band, sort samples by `sample_index`. Convert each `wavelength_um` to
meters:

\[
\lambda_{\mathrm{m}} = \texttt{wavelength\_um} \times 10^{-6}
\]

---

## Trapezoidal response integral

\[
I_R
=
\int R(\lambda)\, d\lambda
\approx
\sum_{j=0}^{M-2}
\frac{R_j + R_{j+1}}{2}
\,(\lambda_{j+1} - \lambda_j)
\]

with \(\lambda\) in meters. \(I_R\) must be strictly positive.

### Scale-invariant accumulation

Response normalization must remain invariant when every response sample is
multiplied by the same positive constant. To avoid loss of precision, use a
common finite positive scale such as

```text
response_scale = max(response_j)
r_j = response_j / response_scale
```

accumulate both trapezoidal sums from the same sorted intervals using `r_j`,
and form their ratio only after accumulation. Multiplying numerator and
denominator back by `response_scale` is unnecessary because it cancels.
Accumulate intervals in increasing `sample_index` order. Mathematically
equivalent compensated summation is allowed. The verifier uses an absolute
scale-invariance tolerance of `1e-8 W m^-2 sr^-1`; it does not require one
language-specific floating-point instruction sequence.

---

## Band radiance

Given surface kinetic temperature \(T_s\) and surface emissivity \(\varepsilon\):

\[
L_{\mathrm{band}}(T_s)
=
\varepsilon
\cdot
\frac{
  \displaystyle\int R(\lambda)\, B_\lambda(\lambda, T_s)\, d\lambda
}{I_R}
\]

Use the same trapezoidal rule on the product \(R(\lambda) B_\lambda(\lambda, T_s)\).

Units of \(L_{\mathrm{band}}\): \(\mathrm{W\,m^{-2}\,sr^{-1}}\) (band-effective
radiance). This value is reported as `band_radiance_w_m2_sr`.

---

## Brightness temperature (without dividing by emissivity)

Brightness temperature \(T_b\) is the blackbody temperature satisfying

\[
\frac{
  \displaystyle\int R(\lambda)\, B_\lambda(\lambda, T_b)\, d\lambda
}{I_R}
=
L_{\mathrm{band}}
\]

**Do not** divide the observed/band radiance by emissivity before solving for
\(T_b\). The left-hand side is a **blackbody** band integral; emissivity enters
only when forming \(L_{\mathrm{band}}\) from the kinetic surface temperature.

### Root finding

- Use a deterministic bracket-preserving method (for example bisection) on
  \([\texttt{minimum\_temperature\_k},\, \texttt{maximum\_temperature\_k}]\).
- Convergence: absolute residual of the normalized blackbody integral versus
  \(L_{\mathrm{band}}\) within `brightness_temperature_tolerance_k`, or at most
  `brightness_temperature_max_iterations` iterations.
- Exact root-iteration histories are **not** compared by the verifier.
- Nonpositive observed radiance yields `minimum_temperature_k`.
- Failure to bracket or produce a finite \(T_b\) is fatal.

---

## Observation evaluation

For each row in `observation_queries.csv`:

1. Take the report-period surface temperature (cell index `0`) at `time_s`.
2. Load the response samples for `band_id`.
3. Compute \(L_{\mathrm{band}}\) with the surface material emissivity.
4. Invert \(T_b\) as above.
5. Emit one `radiometer_rows` entry (see `report_contract.md`) whose
   `observation_id` is the exact CSV identity for that query.

`observation_id` must be copied byte-for-byte from the query file. Do not
synthesize, renumber, normalize, or replace it. Each validated query emits one
radiometer row and the applicable temperature rows.

Observation times must coincide with report-period step end times as required by
`data_contract.md`.
