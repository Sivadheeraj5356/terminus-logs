The FFT's frequency resolution is limited by the bin spacing Δf = sampleRateHz / N. For the default 1000 Hz sample rate and 1024-point FFT, Δf ≈ 0.98 Hz. The current `dominantFrequencyHz` in the JSON report quantizes to the nearest bin center, introducing up to Δf/2 of quantization error. Reduce this error by recovering a sub-bin-accurate frequency estimate from the available spectrum.

Update `compute_dominant_frequency` in `/app/lib/spectral_analyzer.rb` to return an interpolated frequency. Then modify `run!` to also write a short report at `/app/output/interpolation_report.txt` with these lines:

    Peak bin index: <k>
    Peak bin frequency: <f_k> Hz
    Left neighbor magnitude: <m_{k-1}>
    Peak magnitude: <m_k>
    Right neighbor magnitude: <m_{k+1}>
    Interpolated frequency: <f_peak> Hz
    Integer-bin frequency: <f_k> Hz
    Correction: <f_peak - f_k> Hz

The `dominantFrequencyHz` field in the JSON analysis artifact must be the interpolated value. Edge-case bins (peak at index 0 or N/2−1) should fall back to the integer-bin frequency without interpolation.
