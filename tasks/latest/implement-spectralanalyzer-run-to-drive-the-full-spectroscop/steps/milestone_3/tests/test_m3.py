"""Tests for milestone 3: generating golden analysis files."""

import os
import json
import csv
import math
import requests


OUTPUT_DIR = '/app/output'


def test_milestone_2_fix_applied():
    """The .fix-applied marker from milestone 2 must exist."""
    assert os.path.exists('/app/.fix-applied'), \
        '.fix-applied not found — milestone 2 must be completed first'
    r = requests.get('http://localhost:3000/health', timeout=5)
    assert r.status_code == 200, 'API is not running — milestone 2 incomplete'


def test_output_directory_exists():
    """The /app/output directory must exist."""
    assert os.path.isdir(OUTPUT_DIR), '/app/output does not exist'


def test_manifest_exists():
    """The manifest at /app/output/manifest.txt must exist with two lines."""
    assert os.path.exists(f'{OUTPUT_DIR}/manifest.txt'), \
        '/app/output/manifest.txt not found'
    with open(f'{OUTPUT_DIR}/manifest.txt') as f:
        lines = [line.strip() for line in f if line.strip()]
    assert len(lines) == 2, \
        f'Expected 2 files in manifest, got {len(lines)}: {lines}'


def test_json_artifact_exists():
    """The JSON analysis artifact must exist with correct filename and content."""
    json_path = f'{OUTPUT_DIR}/ACCEL-001_analysis.json'
    assert os.path.exists(json_path), \
        f'JSON report must be named ACCEL-001_analysis.json, not at {json_path}'
    with open(json_path) as f:
        data = json.load(f)
    assert 'sensorId' in data, 'ACCEL-001_analysis.json missing sensorId'
    assert 'sampleRateHz' in data, 'ACCEL-001_analysis.json missing sampleRateHz'
    assert 'durationSec' in data, 'ACCEL-001_analysis.json missing durationSec'
    assert 'damping' in data, 'ACCEL-001_analysis.json missing damping'
    assert 'naturalFreqHz' in data, 'ACCEL-001_analysis.json missing naturalFreqHz'
    assert 'rmsEnergy' in data, 'ACCEL-001_analysis.json missing rmsEnergy'
    assert 'dominantFrequencyHz' in data, 'ACCEL-001_analysis.json missing dominantFrequencyHz'
    assert 'numSamples' in data, 'ACCEL-001_analysis.json missing numSamples'
    assert 'apiMetadata' in data, 'ACCEL-001_analysis.json missing apiMetadata'
    assert isinstance(data['sampleRateHz'], (int, float)), \
        'sampleRateHz should be numeric'
    assert isinstance(data['durationSec'], (int, float)), \
        'durationSec should be numeric'
    assert isinstance(data['damping'], (int, float)), \
        'damping should be numeric'
    assert isinstance(data['naturalFreqHz'], (int, float)), \
        'naturalFreqHz should be numeric'
    assert isinstance(data['rmsEnergy'], (int, float)), \
        'rmsEnergy should be numeric'
    assert isinstance(data['dominantFrequencyHz'], (int, float)), \
        'dominantFrequencyHz should be numeric'
    meta = data['apiMetadata']
    assert meta.get('apiVersion') == '1.0.0', \
        f'apiMetadata.apiVersion expected 1.0.0, got {meta.get("apiVersion")}'
    assert meta.get('simulator') == 'damped-oscillator', \
        f'apiMetadata.simulator expected damped-oscillator, got {meta.get("simulator")}'
    assert meta.get('fftMethod') == 'direct', \
        f'apiMetadata.fftMethod expected direct, got {meta.get("fftMethod")}'
    assert meta.get('maxSamples') == 65536, \
        f'apiMetadata.maxSamples expected 65536, got {meta.get("maxSamples")}'


def test_csv_artifact_exists():
    """The CSV spectrum artifact must exist with correct filename and columns."""
    csv_path = f'{OUTPUT_DIR}/ACCEL-001_spectrum.csv'
    assert os.path.exists(csv_path), \
        f'CSV spectrum must be named ACCEL-001_spectrum.csv, not at {csv_path}'
    with open(csv_path) as f:
        reader = csv.reader(f)
        header = next(reader)
    assert header == ['frequencyHz', 'magnitudeDB'], \
        f'CSV header should be [frequencyHz, magnitudeDB], got {header}'


def test_json_rms_energy_reasonable():
    """RMS energy must be a positive finite number (indicating valid computation)."""
    json_path = f'{OUTPUT_DIR}/ACCEL-001_analysis.json'
    assert os.path.exists(json_path), 'ACCEL-001_analysis.json not found'
    with open(json_path) as f:
        data = json.load(f)
    rms = data.get('rmsEnergy', 0)
    assert rms > 0, f'rmsEnergy should be positive, got {rms}'
    assert math.isfinite(rms), f'rmsEnergy should be finite, got {rms}'


def test_csv_has_multiple_rows():
    """CSV must have more than just the header row."""
    csv_path = f'{OUTPUT_DIR}/ACCEL-001_spectrum.csv'
    assert os.path.exists(csv_path), 'ACCEL-001_spectrum.csv not found'
    with open(csv_path) as f:
        reader = csv.reader(f)
        rows = list(reader)
    assert len(rows) > 1, \
        f'CSV should have data rows beyond header, got {len(rows)}'


def test_dominant_frequency_near_natural():
    """Dominant frequency must match the API's peak bin frequency."""
    json_path = f'{OUTPUT_DIR}/ACCEL-001_analysis.json'
    assert os.path.exists(json_path), 'ACCEL-001_analysis.json not found'
    with open(json_path) as f:
        data = json.load(f)
    dom = data.get('dominantFrequencyHz', 0)
    r = requests.post('http://localhost:3000/simulate', json={
        'sampleRateHz': 1000.0, 'durationSec': 0.5,
        'damping': 0.15, 'naturalFreqHz': 50.0
    }, timeout=10)
    api_fft = r.json()['fftBins']
    api_dom = max(api_fft[1:], key=lambda b: b['magnitude'])['frequencyHz']
    assert abs(dom - api_dom) < 0.5, \
        f'dominantFrequencyHz ({dom}) differs from API peak ({api_dom})'


def test_rms_energy_above_threshold():
    """RMS energy must match the value computed from API samples."""
    json_path = f'{OUTPUT_DIR}/ACCEL-001_analysis.json'
    assert os.path.exists(json_path), 'ACCEL-001_analysis.json not found'
    with open(json_path) as f:
        data = json.load(f)
    rms = data.get('rmsEnergy', 0)
    r = requests.post('http://localhost:3000/simulate', json={
        'sampleRateHz': 1000.0, 'durationSec': 2.0,
        'damping': 0.15, 'naturalFreqHz': 50.0
    }, timeout=10)
    api_samples = r.json()['samples']
    mean = sum(api_samples) / len(api_samples)
    expected_rms = math.sqrt(sum((s - mean) ** 2 for s in api_samples) / len(api_samples))
    assert abs(rms - expected_rms) < 0.001, \
        f'rmsEnergy ({rms}) differs from expected ({expected_rms})'


def test_num_samples_correct():
    """numSamples must equal sampleRateHz * durationSec (2000 for default params)."""
    json_path = f'{OUTPUT_DIR}/ACCEL-001_analysis.json'
    assert os.path.exists(json_path), 'ACCEL-001_analysis.json not found'
    with open(json_path) as f:
        data = json.load(f)
    assert data.get('numSamples') == 2000, \
        f'Expected 2000 samples, got {data.get("numSamples")}'


def test_sensor_id_present():
    """sensorId in JSON must match SENSOR_ID from Containerfile."""
    json_path = f'{OUTPUT_DIR}/ACCEL-001_analysis.json'
    assert os.path.exists(json_path), 'ACCEL-001_analysis.json not found'
    with open(json_path) as f:
        data = json.load(f)
    assert data.get('sensorId') == 'ACCEL-001', \
        f'sensorId must match SENSOR_ID from Containerfile, got {data.get("sensorId")}'


def test_manifest_lists_existing_files():
    """Each file listed in manifest must exist in /app/output."""
    with open(f'{OUTPUT_DIR}/manifest.txt') as f:
        filenames = [line.strip() for line in f if line.strip()]
    for fn in filenames:
        full_path = f'{OUTPUT_DIR}/{fn}'
        assert os.path.exists(full_path), \
            f'Manifest lists {fn} but file does not exist at {full_path}'


def test_parseval_theorem_holds():
    """Energy conservation must hold between time and frequency domains.

    Parseval's theorem: sum(|x[n]|^2) = (1/N) * sum(|X[k]|^2)
    for the unnormalized FFT.  The simulated API returns both
    time-domain samples and FFT bins.  Verify the energy in both
    domains matches within 1%.

    This is a fundamental property of the FFT — a violation indicates
    a bug in the FFT implementation or a mismatch between the
    time-domain and frequency-domain data.
    """
    import requests
    API_BASE = 'http://localhost:3000'
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

    # Time-domain energy
    time_energy = sum(s * s for s in samples)

    # Frequency-domain energy from positive half-spectrum
    # |X[0]|^2 + |X[N/2]|^2 + 2 * sum(k=1 to N/2-1) |X[k]|^2
    dc_mag = fft_bins[0]['magnitude']
    nyquist_mag = fft_bins[-1]['magnitude']
    pos_mags = [b['magnitude'] for b in fft_bins[1:-1]]
    freq_energy = (dc_mag**2 + nyquist_mag**2 + 2 * sum(m**2 for m in pos_mags)) / N

    assert abs(time_energy - freq_energy) < 0.01 * time_energy, \
        f'Parseval mismatch: time={time_energy:.4f}, freq={freq_energy:.4f}'


