"""Tests for milestone 2: repairing the Express simulation API."""

import os
import requests


API_BASE = 'http://localhost:3000'


def test_milestone_1_parser_exists():
    """The parse_spec.rb script from milestone 1 must exist."""
    assert os.path.exists('/app/bin/parse_spec.rb'), \
        'parse_spec.rb not found — milestone 1 must be completed first'
    assert os.access('/app/bin/parse_spec.rb', os.X_OK), \
        'parse_spec.rb must be executable'


def test_fix_applied_marker():
    """The fix marker at /app/.fix-applied must exist."""
    assert os.path.exists('/app/.fix-applied'), '.fix-applied not found'


def test_fix_applied_content():
    """The fix marker must contain 'oscillator.ts' and describe the correction."""
    with open('/app/.fix-applied') as f:
        content = f.read()
    assert 'oscillator.ts' in content, \
        'Fix marker should reference oscillator.ts'
    assert len(content) > 20, \
        'Fix marker is too short; should describe the correction'


def test_api_health():
    """The API must respond to GET /health with status ok."""
    r = requests.get(f'{API_BASE}/health', timeout=5)
    assert r.status_code == 200
    data = r.json()
    assert data['status'] == 'ok', f'Expected ok, got {data}'


def test_simulate_returns_samples():
    """POST /simulate must return samples and fftBins."""
    payload = {
        'sampleRateHz': 1000.0,
        'durationSec': 0.5,
        'damping': 0.15,
        'naturalFreqHz': 50.0
    }
    r = requests.post(f'{API_BASE}/simulate', json=payload, timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert 'samples' in data, 'Missing samples in response'
    assert 'fftBins' in data, 'Missing fftBins in response'
    assert len(data['samples']) == 500, \
        f'Expected 500 samples for 0.5s at 1000Hz, got {len(data["samples"])}'


def test_damping_term_corrected():
    """The damping decay must use angular frequency (wn), not naturalFreqHz.
    
    With damping 0.5 and natural frequency 30 Hz, the sample at index 30
    (t = 0.03s at 1000 Hz) should have an envelope of exp(-0.5 * 2*pi*30 * 0.03)
    = exp(-2.827) ≈ 0.059. With the bug (Hz instead of rad/s), the envelope
    would be exp(-0.5 * 30 * 0.03) = exp(-0.45) ≈ 0.638. We verify the fix
    by confirming the absolute sample value is below the midpoint.
    """
    payload = {
        'sampleRateHz': 1000.0,
        'durationSec': 0.5,
        'damping': 0.5,
        'naturalFreqHz': 30.0
    }
    r = requests.post(f'{API_BASE}/simulate', json=payload, timeout=10)
    samples = r.json()['samples']
    val_at_idx_30 = abs(samples[30])

    # With fix: envelope ≈ 0.059, with bug: envelope ≈ 0.638
    # Midpoint is ~0.35. Use 0.3 as threshold.
    assert val_at_idx_30 < 0.3, \
        f'Sample at index 30 has magnitude {val_at_idx_30} (too large, bug likely still present)'


def test_fft_magnitude_includes_imaginary():
    """FFT magnitude must include both real and imaginary components.

    Parseval's theorem requires the energy in the time domain to match
    the energy in the frequency domain. If the magnitude calculation
    discards the imaginary part (using only Math.abs(real)), the
    frequency-domain energy will be significantly lower.
    """
    payload = {
        'sampleRateHz': 1000.0,
        'durationSec': 0.5,
        'damping': 0.15,
        'naturalFreqHz': 50.0
    }
    r = requests.post(f'{API_BASE}/simulate', json=payload, timeout=10)
    data = r.json()
    samples = data['samples']
    fft_bins = data['fftBins']

    N = len(fft_bins) * 2
    time_energy = sum(s * s for s in samples)
    dc_mag = fft_bins[0]['magnitude']
    nyquist_mag = fft_bins[-1]['magnitude']
    pos_mags = [b['magnitude'] for b in fft_bins[1:-1]]
    freq_energy = (dc_mag**2 + nyquist_mag**2 + 2 * sum(m**2 for m in pos_mags)) / N

    assert abs(time_energy - freq_energy) < 0.01 * time_energy, \
        f'Parseval mismatch: time={time_energy:.4f}, freq={freq_energy:.4f}'


def test_samples_have_zero_mean():
    """Simulated samples must have approximately zero mean (no DC bias).

    A DC offset would corrupt downstream spectral analysis by
    injecting energy at 0 Hz.  Verify the mean of the entire
    sample window is below 0.01.
    """
    payload = {
        'sampleRateHz': 1000.0,
        'durationSec': 0.5,
        'damping': 0.15,
        'naturalFreqHz': 50.0
    }
    r = requests.post(f'{API_BASE}/simulate', json=payload, timeout=10)
    samples = r.json()['samples']
    mean = sum(samples) / len(samples)
    assert abs(mean) < 0.01, \
        f'Sample mean should be near zero, got {mean:.6f} (DC bias present)'


