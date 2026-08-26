"""Tests for milestone 1: Containerfile parsing."""

import subprocess
import re
import os
import tempfile


def test_parse_script_exists():
    """The parse script /app/bin/parse_spec.rb must exist and be executable."""
    assert os.path.exists('/app/bin/parse_spec.rb'), \
        'parse_spec.rb not found'
    assert os.access('/app/bin/parse_spec.rb', os.X_OK), \
        'parse_spec.rb must be executable'


def test_parse_script_outputs_expected_keys():
    """The parse script must output all five Containerfile parameters."""
    result = subprocess.run(
        ['/app/bin/parse_spec.rb'],
        capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 0, \
        f'Script exited with code {result.returncode}: {result.stderr}'
    lines = result.stdout.strip().split('\n')
    keys = {}
    for line in lines:
        m = re.match(r'^(\w[\w_]*)\s*:\s*(.+)$', line)
        if m:
            keys[m.group(1)] = m.group(2).strip()
    assert keys.get('sensor_frequency_hz') == '1000.0', \
        f'sensor_frequency_hz: expected 1000.0, got {keys.get("sensor_frequency_hz")}'
    assert keys.get('sample_duration_sec') == '2.0', \
        f'sample_duration_sec: expected 2.0, got {keys.get("sample_duration_sec")}'
    assert keys.get('damping_coefficient') == '0.15', \
        f'damping_coefficient: expected 0.15, got {keys.get("damping_coefficient")}'
    assert keys.get('natural_frequency_hz') == '50.0', \
        f'natural_frequency_hz: expected 50.0, got {keys.get("natural_frequency_hz")}'
    assert keys.get('sensor_id') == 'ACCEL-001', \
        f'sensor_id: expected ACCEL-001, got {keys.get("sensor_id")}'


def test_parse_script_fails_on_missing_file():
    """The parse script must exit with code 1 when the Containerfile is missing."""
    result = subprocess.run(
        ['/app/bin/parse_spec.rb', '/app/nonexistent_file.CONTAINERFILE'],
        capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 1, \
        f'Expected exit code 1 for missing file, got {result.returncode}'


def test_library_method_returns_correct_hash():
    """Running parse_spec.rb on the real Containerfile produces all expected keys with symbol-style names."""
    result = subprocess.run(
        ['/app/bin/parse_spec.rb'],
        capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 0, \
        f'Script exited with code {result.returncode}: {result.stderr}'
    assert 'sensor_frequency_hz' in result.stdout, \
        'Missing key sensor_frequency_hz in output'
    assert 'sensor_id' in result.stdout, \
        'Missing key sensor_id in output'
    assert re.search(r'sensor_frequency_hz\s*:\s*1000\.0', result.stdout), \
        'sensor_frequency_hz should be 1000.0'


def test_parse_handles_empty_value():
    """A parameter with no value (e.g. EMPTY_VARIABLE=) should parse with empty string via the CLI."""
    content = "EMPTY_VARIABLE=\n"
    with tempfile.NamedTemporaryFile(mode='w', suffix='.cfg', delete=False) as f:
        f.write(content)
        tmp_path = f.name
    try:
        result = subprocess.run(
            ['/app/bin/parse_spec.rb', tmp_path],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0, f'CLI failed: {result.stderr}'
        assert 'empty_variable' in result.stdout, \
            'Empty value param should produce key empty_variable in output'
    finally:
        os.unlink(tmp_path)


def test_parse_keeps_hash_in_value():
    """A # character mid-line is part of the value, not a comment, verified via the CLI."""
    content = "TOKEN=abc#def\n"
    with tempfile.NamedTemporaryFile(mode='w', suffix='.cfg', delete=False) as f:
        f.write(content)
        tmp_path = f.name
    try:
        result = subprocess.run(
            ['/app/bin/parse_spec.rb', tmp_path],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0, f'CLI failed: {result.stderr}'
        lines = result.stdout.strip().split('\n')
        for line in lines:
            m = re.match(r'^(\w[\w_]*)\s*:\s*(.+)$', line)
            if m and m.group(1) == 'token':
                assert m.group(2).strip() == 'abc#def', \
                    f'Token with # expected abc#def, got {m.group(2).strip()!r}'
                break
        else:
            assert False, 'token key not found in output'
    finally:
        os.unlink(tmp_path)


def test_parse_skips_whitespace_lines():
    """Lines containing only whitespace are ignored (not treated as params), verified via CLI."""
    content = "A=1\n   \nB=2\n"
    with tempfile.NamedTemporaryFile(mode='w', suffix='.cfg', delete=False) as f:
        f.write(content)
        tmp_path = f.name
    try:
        result = subprocess.run(
            ['/app/bin/parse_spec.rb', tmp_path],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0, f'CLI failed: {result.stderr}'
        lines = [line for line in result.stdout.strip().split('\n') if re.match(r'^\w', line)]
        assert len(lines) == 2, \
            f'Expected 2 keys (a, b), got {len(lines)}: {lines}'
    finally:
        os.unlink(tmp_path)


def test_parse_trims_surrounding_whitespace():
    """Keys and values with surrounding whitespace must be trimmed, verified via CLI."""
    content = "  KEY_ONE  =   value_one  \n\tKEY_TWO=\tvalue_two\t\n"
    with tempfile.NamedTemporaryFile(mode='w', suffix='.cfg', delete=False) as f:
        f.write(content)
        tmp_path = f.name
    try:
        result = subprocess.run(
            ['/app/bin/parse_spec.rb', tmp_path],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0, f'CLI failed: {result.stderr}'
        lines = result.stdout.strip().split('\n')
        keys = {}
        for line in lines:
            m = re.match(r'^(\w[\w_]*)\s*:\s*(.+)$', line)
            if m:
                keys[m.group(1)] = m.group(2).strip()
        assert keys.get('key_one') == 'value_one', \
            f'Expected key_one=value_one, got {keys.get("key_one")}'
        assert keys.get('key_two') == 'value_two', \
            f'Expected key_two=value_two, got {keys.get("key_two")}'
    finally:
        os.unlink(tmp_path)
