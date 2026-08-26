"""Tests for milestone 4: validation and diagnostics."""

import os
import json
import subprocess
import tempfile
import pytest


OUTPUT_DIR = '/app/output'


def test_milestone_3_artifacts_exist():
    """Pipeline output artifacts from milestone 3 must exist."""
    assert os.path.isdir(OUTPUT_DIR), '/app/output does not exist'
    assert os.path.exists(f'{OUTPUT_DIR}/manifest.txt'), \
        'manifest.txt not found — milestone 3 must be completed first'
    has_json = any(f.endswith('.json') for f in os.listdir(OUTPUT_DIR))
    has_csv = any(f.endswith('.csv') for f in os.listdir(OUTPUT_DIR))
    assert has_json, 'No JSON analysis artifact found — milestone 3 incomplete'
    assert has_csv, 'No CSV spectrum artifact found — milestone 3 incomplete'


def test_validate_config_method_exists():
    """SpectralAnalyzer must respond to validate_config by checking it returns a Hash."""
    code = 'require "json"; require "/app/lib/spectral_analyzer"; sa = SpectralAnalyzer.new("/app/Containerfile", "http://localhost:3000"); r = sa.validate_config; puts r.class; puts r[:valid].inspect'
    with tempfile.NamedTemporaryFile(mode='w', suffix='.rb', delete=False) as f:
        f.write(code)
        script_path = f.name
    try:
        result = subprocess.run(
            ['ruby', script_path],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0, f'Ruby script failed: {result.stderr}'
        assert 'Hash' in result.stdout, 'validate_config should return a Hash'
        assert 'true' in result.stdout or 'false' in result.stdout, \
            'validate_config should return :valid boolean'
    finally:
        os.unlink(script_path)


def test_validate_config_with_defaults():
    """Default Containerfile params should pass validation."""
    code = 'require "json"; require "/app/lib/spectral_analyzer"; sa = SpectralAnalyzer.new("/app/Containerfile", "http://localhost:3000"); r = sa.validate_config; puts r[:valid]; puts r[:errors].length'
    with tempfile.NamedTemporaryFile(mode='w', suffix='.rb', delete=False) as f:
        f.write(code)
        script_path = f.name
    try:
        result = subprocess.run(
            ['ruby', script_path],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0, f'Ruby script failed: {result.stderr}'
        lines = result.stdout.strip().split('\n')
        assert lines[0] == 'true', f'Expected valid=true, got {lines[0]}'
        assert lines[1] == '0', f'Expected 0 errors, got {lines[1]}'
    finally:
        os.unlink(script_path)


def test_debug_report_generated():
    """generate_debug_report must write to /app/debug_report.json."""
    code = 'require "json"; require "/app/lib/spectral_analyzer"; sa = SpectralAnalyzer.new("/app/Containerfile", "http://localhost:3000"); sa.generate_debug_report'
    with tempfile.NamedTemporaryFile(mode='w', suffix='.rb', delete=False) as f:
        f.write(code)
        script_path = f.name
    try:
        result = subprocess.run(
            ['ruby', script_path],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0, f'Ruby script failed: {result.stderr}'
        assert os.path.exists('/app/debug_report.json'), \
            'debug_report.json was not created'
        with open('/app/debug_report.json') as f:
            report = json.load(f)
        assert 'parameters' in report, 'Missing parameters in debug report'
        assert 'validation' in report, 'Missing validation in debug report'
        assert 'valid' in report['validation'], 'Missing validation.valid in debug report'
        assert 'errors' in report['validation'], 'Missing validation.errors in debug report'
        assert 'timestamp' in report, 'Missing timestamp in debug report'
    finally:
        os.unlink(script_path)


def test_validation_spec_exists():
    """Validation spec documentation must exist."""
    spec_paths = [
        '/app/docs/validation_spec.md',
    ]
    found = False
    for p in spec_paths:
        if os.path.exists(p):
            found = True
            with open(p) as f:
                content = f.read()
            assert len(content) > 20, \
                f'{p} is too short; should document range constraints'
            break
    assert found, 'validation_spec.md not found in /app/docs/'


def test_debug_report_contains_parameters():
    """Debug report must include experiment parameters."""
    if not os.path.exists('/app/debug_report.json'):
        pytest.skip('debug_report.json not found')
    with open('/app/debug_report.json') as f:
        report = json.load(f)
    params = report.get('parameters', {})
    assert len(params) > 0, 'parameters should not be empty'


def test_validate_config_rejects_natural_freq_above_nyquist():
    """naturalFreqHz > sampleRateHz / 2 violates the Nyquist criterion."""
    code = '''
require "json"
require "/app/lib/spectral_analyzer"
require "tempfile"
content = <<~CFG
SENSOR_FREQUENCY_HZ=100.0
SAMPLE_DURATION_SEC=1.0
DAMPING_COEFFICIENT=0.1
NATURAL_FREQUENCY_HZ=80.0
SENSOR_ID=ACCEL-002
CFG
f = Tempfile.new(%w[containerfile .cfg])
f.write(content)
f.close
sa = SpectralAnalyzer.new(f.path, "http://localhost:3000")
r = sa.validate_config
puts r[:valid]
puts r[:errors].length
f.unlink
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
        lines = result.stdout.strip().split('\n')
        assert lines[0] == 'false', \
            f'Expected valid=false for Nyquist violation, got {lines[0]}'
        assert lines[1] != '0', \
            'Expected at least one error for Nyquist violation'
    finally:
        os.unlink(script_path)


def test_validate_config_rejects_out_of_range_damping():
    """Damping coefficient outside [0, 1] must be rejected."""
    code = '''
require "json"
require "/app/lib/spectral_analyzer"
require "tempfile"
content = <<~CFG
SENSOR_FREQUENCY_HZ=1000.0
SAMPLE_DURATION_SEC=1.0
DAMPING_COEFFICIENT=1.5
NATURAL_FREQUENCY_HZ=50.0
SENSOR_ID=ACCEL-003
CFG
f = Tempfile.new(%w[containerfile .cfg])
f.write(content)
f.close
sa = SpectralAnalyzer.new(f.path, "http://localhost:3000")
r = sa.validate_config
puts r[:valid]
puts r[:errors].length
f.unlink
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
        lines = result.stdout.strip().split('\n')
        assert lines[0] == 'false', \
            f'Expected valid=false for damping=1.5, got {lines[0]}'
        assert lines[1] != '0', \
            'Expected at least one error for out-of-range damping'
    finally:
        os.unlink(script_path)


def test_validate_config_rejects_sample_rate_below_minimum():
    """Sample rate below 100 Hz must be rejected."""
    code = '''
require "json"
require "/app/lib/spectral_analyzer"
require "tempfile"
content = <<~CFG
SENSOR_FREQUENCY_HZ=50.0
SAMPLE_DURATION_SEC=1.0
DAMPING_COEFFICIENT=0.1
NATURAL_FREQUENCY_HZ=20.0
SENSOR_ID=ACCEL-004
CFG
f = Tempfile.new(%w[containerfile .cfg])
f.write(content)
f.close
sa = SpectralAnalyzer.new(f.path, "http://localhost:3000")
r = sa.validate_config
puts r[:valid]
puts r[:errors].length
f.unlink
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
        lines = result.stdout.strip().split('\n')
        assert lines[0] == 'false', \
            f'Expected valid=false for sensor_frequency_hz=50.0, got {lines[0]}'
    finally:
        os.unlink(script_path)


def test_validate_config_rejects_sample_rate_above_maximum():
    """Sample rate above 10000 Hz must be rejected."""
    code = '''
require "json"
require "/app/lib/spectral_analyzer"
require "tempfile"
content = <<~CFG
SENSOR_FREQUENCY_HZ=20000.0
SAMPLE_DURATION_SEC=1.0
DAMPING_COEFFICIENT=0.1
NATURAL_FREQUENCY_HZ=50.0
SENSOR_ID=ACCEL-005
CFG
f = Tempfile.new(%w[containerfile .cfg])
f.write(content)
f.close
sa = SpectralAnalyzer.new(f.path, "http://localhost:3000")
r = sa.validate_config
puts r[:valid]
puts r[:errors].length
f.unlink
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
        lines = result.stdout.strip().split('\n')
        assert lines[0] == 'false', \
            f'Expected valid=false for sensor_frequency_hz=20000.0, got {lines[0]}'
    finally:
        os.unlink(script_path)


def test_validate_config_rejects_duration_below_minimum():
    """Duration below 0.1 s must be rejected."""
    code = '''
require "json"
require "/app/lib/spectral_analyzer"
require "tempfile"
content = <<~CFG
SENSOR_FREQUENCY_HZ=1000.0
SAMPLE_DURATION_SEC=0.05
DAMPING_COEFFICIENT=0.1
NATURAL_FREQUENCY_HZ=50.0
SENSOR_ID=ACCEL-006
CFG
f = Tempfile.new(%w[containerfile .cfg])
f.write(content)
f.close
sa = SpectralAnalyzer.new(f.path, "http://localhost:3000")
r = sa.validate_config
puts r[:valid]
puts r[:errors].length
f.unlink
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
        lines = result.stdout.strip().split('\n')
        assert lines[0] == 'false', \
            f'Expected valid=false for sample_duration_sec=0.05, got {lines[0]}'
    finally:
        os.unlink(script_path)


def test_validate_config_rejects_duration_above_maximum():
    """Duration above 60 s must be rejected."""
    code = '''
require "json"
require "/app/lib/spectral_analyzer"
require "tempfile"
content = <<~CFG
SENSOR_FREQUENCY_HZ=1000.0
SAMPLE_DURATION_SEC=120.0
DAMPING_COEFFICIENT=0.1
NATURAL_FREQUENCY_HZ=50.0
SENSOR_ID=ACCEL-007
CFG
f = Tempfile.new(%w[containerfile .cfg])
f.write(content)
f.close
sa = SpectralAnalyzer.new(f.path, "http://localhost:3000")
r = sa.validate_config
puts r[:valid]
puts r[:errors].length
f.unlink
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
        lines = result.stdout.strip().split('\n')
        assert lines[0] == 'false', \
            f'Expected valid=false for sample_duration_sec=120.0, got {lines[0]}'
    finally:
        os.unlink(script_path)


def test_validate_config_rejects_natural_freq_below_minimum():
    """Natural frequency below 1 Hz must be rejected."""
    code = '''
require "json"
require "/app/lib/spectral_analyzer"
require "tempfile"
content = <<~CFG
SENSOR_FREQUENCY_HZ=1000.0
SAMPLE_DURATION_SEC=1.0
DAMPING_COEFFICIENT=0.1
NATURAL_FREQUENCY_HZ=0.5
SENSOR_ID=ACCEL-008
CFG
f = Tempfile.new(%w[containerfile .cfg])
f.write(content)
f.close
sa = SpectralAnalyzer.new(f.path, "http://localhost:3000")
r = sa.validate_config
puts r[:valid]
puts r[:errors].length
f.unlink
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
        lines = result.stdout.strip().split('\n')
        assert lines[0] == 'false', \
            f'Expected valid=false for natural_frequency_hz=0.5, got {lines[0]}'
    finally:
        os.unlink(script_path)


def test_validate_config_rejects_natural_freq_above_maximum():
    """Natural frequency above 1000 Hz must be rejected."""
    code = '''
require "json"
require "/app/lib/spectral_analyzer"
require "tempfile"
content = <<~CFG
SENSOR_FREQUENCY_HZ=10000.0
SAMPLE_DURATION_SEC=1.0
DAMPING_COEFFICIENT=0.1
NATURAL_FREQUENCY_HZ=2000.0
SENSOR_ID=ACCEL-009
CFG
f = Tempfile.new(%w[containerfile .cfg])
f.write(content)
f.close
sa = SpectralAnalyzer.new(f.path, "http://localhost:3000")
r = sa.validate_config
puts r[:valid]
puts r[:errors].length
f.unlink
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
        lines = result.stdout.strip().split('\n')
        assert lines[0] == 'false', \
            f'Expected valid=false for natural_frequency_hz=2000.0, got {lines[0]}'
    finally:
        os.unlink(script_path)


def test_validate_config_rejects_invalid_sensor_id():
    """Sensor ID not matching ACCEL-XXX pattern must be rejected."""
    code = '''
require "json"
require "/app/lib/spectral_analyzer"
require "tempfile"
content = <<~CFG
SENSOR_FREQUENCY_HZ=1000.0
SAMPLE_DURATION_SEC=1.0
DAMPING_COEFFICIENT=0.1
NATURAL_FREQUENCY_HZ=50.0
SENSOR_ID=SENS-01
CFG
f = Tempfile.new(%w[containerfile .cfg])
f.write(content)
f.close
sa = SpectralAnalyzer.new(f.path, "http://localhost:3000")
r = sa.validate_config
puts r[:valid]
puts r[:errors].length
f.unlink
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
        lines = result.stdout.strip().split('\n')
        assert lines[0] == 'false', \
            f'Expected valid=false for sensor_id=SENS-01, got {lines[0]}'
    finally:
        os.unlink(script_path)
