"""Tests for milestone 5: sub-bin frequency interpolation."""

import os
import json
import math
import subprocess
import tempfile


OUTPUT_DIR = '/app/output'


def test_milestone_3_artifacts_exist():
    """Pipeline output artifacts from milestone 3 must exist."""
    assert os.path.isdir(OUTPUT_DIR), '/app/output does not exist'
    assert os.path.exists(f'{OUTPUT_DIR}/manifest.txt'), \
        'manifest.txt not found — milestone 3 must be completed first'
    has_json = any(f.endswith('.json') and f != 'debug_report.json'
                   for f in os.listdir(OUTPUT_DIR))
    has_csv = any(f.endswith('.csv') for f in os.listdir(OUTPUT_DIR))
    assert has_json, 'No JSON analysis artifact found — milestone 3 incomplete'
    assert has_csv, 'No CSV spectrum artifact found — milestone 3 incomplete'


def test_analysis_json_exists():
    """The JSON analysis artifact must exist."""
    for fname in os.listdir(OUTPUT_DIR):
        if fname.endswith('.json') and fname != 'debug_report.json':
            with open(f'{OUTPUT_DIR}/{fname}') as f:
                data = json.load(f)
            assert 'dominantFrequencyHz' in data
            break
    else:
        assert False, 'No JSON analysis artifact found'


def test_interpolation_report_exists():
    """The interpolation report must exist and have the required fields."""
    assert os.path.exists(f'{OUTPUT_DIR}/interpolation_report.txt'), \
        '/app/output/interpolation_report.txt not found'
    with open(f'{OUTPUT_DIR}/interpolation_report.txt') as f:
        content = f.read()
    for field in ['Peak bin index', 'Peak bin frequency',
                  'Left neighbor magnitude', 'Peak magnitude',
                  'Right neighbor magnitude', 'Interpolated frequency',
                  'Integer-bin frequency', 'Correction']:
        assert field in content, \
            f'interpolation_report.txt missing field: {field}'


def test_interpolated_closer_than_integer_bin():
    """Interpolated frequency must be closer to the damped natural frequency
    (~49.44 Hz) than the integer-bin frequency is, confirming the parabolic
    interpolation is working correctly.
    """
    with open(f'{OUTPUT_DIR}/interpolation_report.txt') as f:
        content = f.read()
    interpolated = None
    integer_bin = None
    for line in content.split('\n'):
        if 'Interpolated frequency' in line:
            interpolated = float(line.split(':')[1].strip().split()[0])
        if 'Integer-bin frequency' in line:
            integer_bin = float(line.split(':')[1].strip().split()[0])
    assert interpolated is not None, 'Could not find Interpolated frequency'
    assert integer_bin is not None, 'Could not find Integer-bin frequency'
    damped_natural = 50.0 * math.sqrt(1 - 0.15**2)
    interp_error = abs(interpolated - damped_natural)
    bin_error = abs(integer_bin - damped_natural)
    assert interp_error < bin_error, \
        f'Interpolated error ({interp_error:.4f}) >= integer-bin error ({bin_error:.4f})'


def test_interpolation_correction_nonzero():
    """The correction value should be non-zero (interpolation changed the bin-center value)."""
    with open(f'{OUTPUT_DIR}/interpolation_report.txt') as f:
        content = f.read()
    for line in content.split('\n'):
        if 'Correction' in line:
            correction_str = line.split(':')[1].strip().split()[0]
            correction = float(correction_str)
            break
    else:
        assert False, 'Could not find Correction in report'
    assert abs(correction) > 1e-6, \
        f'Correction {correction} is essentially zero — interpolation may not be applied'


def test_json_dominant_matches_interpolated():
    """dominantFrequencyHz in JSON must match the interpolated frequency from the report."""
    with open(f'{OUTPUT_DIR}/interpolation_report.txt') as f:
        content = f.read()
    for line in content.split('\n'):
        if 'Interpolated frequency' in line:
            freq_str = line.split(':')[1].strip().split()[0]
            interpolated = float(freq_str)
            break
    else:
        assert False, 'Could not find Interpolated frequency in report'
    for fname in os.listdir(OUTPUT_DIR):
        if not fname.endswith('.json') or fname == 'debug_report.json':
            continue
        with open(f'{OUTPUT_DIR}/{fname}') as f:
            data = json.load(f)
        json_freq = data.get('dominantFrequencyHz')
        assert abs(json_freq - interpolated) < 0.01, \
            f'JSON dominantFrequencyHz ({json_freq}) differs from interpolated ({interpolated})'


def test_fallback_for_edge_peak():
    """If the spectral peak is at the last bin (Nyquist), interpolation should fall back."""
    code = '''
require "json"
require "/app/lib/spectral_analyzer"
data_edge = {
  "fftBins" => [
    {"frequencyHz" => 0.0,   "magnitude" => 0.01},
    {"frequencyHz" => 10.0,  "magnitude" => 0.02},
    {"frequencyHz" => 20.0,  "magnitude" => 10.0}
  ]
}
sa = SpectralAnalyzer.new("/app/Containerfile", "http://localhost:3000")
result = sa.compute_dominant_frequency(data_edge)
puts "edge_result=#{result}"
'''
    with tempfile.NamedTemporaryFile(mode='w', suffix='.rb', delete=False) as f:
        f.write(code)
        script_path = f.name
    try:
        result = subprocess.run(
            ['ruby', script_path],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0, f'Ruby script failed: {result.stderr}'
        assert 'edge_result=20.0' in result.stdout, \
            f'Expected fallback to 20.0 for Nyquist-edge peak, got: {result.stdout}'
    finally:
        os.unlink(script_path)
