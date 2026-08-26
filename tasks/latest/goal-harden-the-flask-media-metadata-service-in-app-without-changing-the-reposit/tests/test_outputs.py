import hashlib
import json
import os
import re
import socket
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest
import requests
import yaml
from PIL import Image

APP = Path('/app')
CONFIG = APP / 'config' / 'media.yaml'
REPORT = APP / 'build' / 'hardened-report.json'
PINNED_YQ_VERSION = 'v4.53.3'
PINNED_YQ_SHA256 = '84be51c2bf82b1eae16c54fab3f5d9aa887f5fb30d90990217e9031bf42f9f56'
ALLOWED_ORIGIN = 'https://media.example.test'
API_KEY_HEADER = 'X-API-Key'
API_KEY = 'media-local-build-token'
ITEM_KEYS = ['name', 'format', 'width', 'height', 'mode']
REASON_ORDER = ['missing_manifest', 'sha256', 'signature', 'format', 'width', 'height', 'mode', 'pixels', 'name_collision']
MANIFEST_FIELD_ORDER = ['sha256', 'signature', 'format', 'width', 'height', 'mode']
MANIFEST_SIGNATURE_KEYS = ['name', 'sha256', 'format', 'width', 'height', 'mode']
DEFAULT_WEIGHTS = {
    'missing_manifest': 13,
    'sha256': 11,
    'signature': 7,
    'format': 5,
    'width': 5,
    'height': 5,
    'mode': 5,
    'pixels': 3,
    'name_collision': 17,
}


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def run(cmd, **kwargs):
    kwargs.setdefault('cwd', APP)
    kwargs.setdefault('text', True)
    kwargs.setdefault('capture_output', True)
    kwargs.setdefault('timeout', 120)
    proc = subprocess.run(cmd, **kwargs)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return proc


def run_report_expect_failure():
    proc = subprocess.run(
        ['make', 'report', f'PORT={free_port()}'],
        cwd=APP,
        text=True,
        capture_output=True,
        timeout=180,
    )
    assert proc.returncode != 0, 'make report must fail when manifest or policy validation fails'
    assert REPORT.exists(), 'failed validation should still write build/hardened-report.json'
    return json.loads(REPORT.read_text())


def wait_for(url, timeout=15):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            response = requests.get(url, timeout=1)
            if response.status_code == 200:
                return response
            last = f'status {response.status_code}: {response.text}'
        except Exception as exc:
            last = repr(exc)
        time.sleep(0.25)
    raise AssertionError(f'service did not become ready at {url}: {last}')


def compact_catalog_digest(items):
    canonical = [{key: item[key] for key in ITEM_KEYS} for item in items]
    blob = json.dumps(canonical, separators=(',', ':'))
    return hashlib.sha256(blob.encode()).hexdigest()


def manifest_signature(entry):
    text = '\n'.join(['media-manifest-v1'] + [str(entry[key]) for key in MANIFEST_SIGNATURE_KEYS]) + '\n'
    return hashlib.sha256(text.encode()).hexdigest()


def manifest_entry_for(path):
    with Image.open(path) as image:
        entry = {
            'name': path.name,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'format': image.format,
            'width': image.width,
            'height': image.height,
            'mode': image.mode,
        }
    entry['signature'] = manifest_signature(entry)
    return entry


def fixture_records():
    records = []
    for path in sorted((APP / 'fixtures').iterdir(), key=lambda p: p.name):
        if path.suffix.lower() not in {'.png', '.jpg', '.jpeg'} or not path.is_file():
            continue
        with Image.open(path) as image:
            records.append({
                'name': path.name,
                'format': image.format,
                'width': image.width,
                'height': image.height,
                'mode': image.mode,
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            })
    return records


def content_hashes():
    return {record['name']: record['sha256'] for record in fixture_records()}


def collision_id(name):
    stem = Path(name).stem.lower()
    return re.sub(r'[^a-z0-9]+', '-', stem).strip('-')


def policy_expectations(config=None):
    if config is None:
        config = yaml.safe_load(CONFIG.read_text())
    manifest = {entry['name']: entry for entry in config['media']['manifest']}
    policy = config['media']['policy']
    weights = {**DEFAULT_WEIGHTS, **policy.get('reason_weights', {})}
    max_pixels = int(policy['max_pixels'])
    records = fixture_records()
    ids = {}
    for record in records:
        ids.setdefault(collision_id(record['name']), []).append(record['name'])
    colliding = {name for names in ids.values() if len(names) > 1 for name in names}
    accepted = []
    quarantined = []
    for record in records:
        reasons = []
        entry = manifest.get(record['name'])
        if entry is None:
            reasons.append('missing_manifest')
        else:
            if entry.get('sha256') != record['sha256']:
                reasons.append('sha256')
            if entry.get('signature') != manifest_signature(entry):
                reasons.append('signature')
            for field in ('format', 'width', 'height', 'mode'):
                if str(entry.get(field)) != str(record[field]):
                    reasons.append(field)
        if record['width'] * record['height'] > max_pixels:
            reasons.append('pixels')
        if record['name'] in colliding:
            reasons.append('name_collision')
        reasons = [reason for reason in REASON_ORDER if reason in set(reasons)]
        item = {key: record[key] for key in ITEM_KEYS}
        if reasons:
            quarantined.append({'name': record['name'], 'reasons': reasons})
        else:
            accepted.append(item)
    risk_score = sum(weights[reason] for q in quarantined for reason in q['reasons'])
    return {
        'accepted_items': sorted(accepted, key=lambda x: x['name']),
        'accepted_names': sorted(item['name'] for item in accepted),
        'quarantined': sorted(quarantined, key=lambda x: x['name']),
        'risk_score': risk_score,
    }


def expected_manifest(config=None):
    if config is None:
        config = yaml.safe_load(CONFIG.read_text())
    records = {record['name']: record for record in fixture_records()}
    manifest = {entry['name']: entry for entry in config['media']['manifest']}
    expected_names = sorted(manifest)
    missing = sorted(name for name in manifest if name not in records)
    unexpected = sorted(name for name in records if name not in manifest)
    mismatches = []
    for name in sorted(set(records) & set(manifest)):
        entry = manifest[name]
        record = records[name]
        fields = []
        if entry.get('sha256') != record['sha256']:
            fields.append('sha256')
        if entry.get('signature') != manifest_signature(entry):
            fields.append('signature')
        for field in ('format', 'width', 'height', 'mode'):
            if str(entry.get(field)) != str(record[field]):
                fields.append(field)
        if fields:
            mismatches.append({'name': name, 'fields': sorted(fields, key=MANIFEST_FIELD_ORDER.index)})
    return {
        'declared_count': len(config['media']['manifest']),
        'expected_names': expected_names,
        'missing_files': missing,
        'unexpected_files': unexpected,
        'mismatches': mismatches,
        'content_sha256': content_hashes(),
        'passed': not missing and not unexpected and not mismatches,
    }


def merkle_root(items, hashes):
    leaves = []
    for item in items:
        name = item['name']
        text = '\n'.join(['media-leaf-v2', name, item['format'], str(item['width']), str(item['height']), item['mode'], hashes[name]]) + '\n'
        leaves.append(hashlib.sha256(text.encode()).hexdigest())
    if not leaves:
        return hashlib.sha256(b'media-empty-v2\n').hexdigest()
    while len(leaves) > 1:
        nxt = []
        for i in range(0, len(leaves), 2):
            left = leaves[i]
            right = leaves[i + 1] if i + 1 < len(leaves) else left
            nxt.append(hashlib.sha256(f'media-node-v2\n{left}\n{right}\n'.encode()).hexdigest())
        leaves = nxt
    return leaves[0]


def assert_exact_report_schema(report):
    assert set(report) == {'security', 'yq', 'tools', 'config', 'api', 'manifest', 'policy'}
    assert set(report['security']) == {'passed'}
    assert set(report['yq']) == {'version', 'sha256', 'path', 'version_output'}
    assert set(report['tools']) == {'yq_used', 'jq_used'}
    assert set(report['config']) == {'debug', 'host', 'cors_wildcard', 'leaks_absolute_paths'}
    assert set(report['api']) == {'health_status', 'debug', 'auth_required', 'unauthorized_status', 'media_count', 'absolute_path_leaks', 'formats', 'catalog_sha256'}
    assert set(report['manifest']) == {'declared_count', 'expected_names', 'missing_files', 'unexpected_files', 'mismatches', 'content_sha256', 'passed'}
    assert set(report['policy']) == {'passed', 'accepted_names', 'quarantined', 'risk_score', 'catalog_merkle_root'}
    assert isinstance(report['security']['passed'], bool)
    for key in ('version', 'sha256', 'path', 'version_output'):
        assert isinstance(report['yq'][key], str)
    assert report['tools']['yq_used'] is True
    assert report['tools']['jq_used'] is True
    assert isinstance(report['config']['debug'], bool)
    assert isinstance(report['config']['host'], str)
    assert isinstance(report['config']['cors_wildcard'], bool)
    assert isinstance(report['config']['leaks_absolute_paths'], bool)
    assert isinstance(report['api']['health_status'], str)
    assert isinstance(report['api']['debug'], bool)
    assert report['api']['auth_required'] is True
    assert isinstance(report['api']['unauthorized_status'], int)
    assert isinstance(report['api']['media_count'], int)
    assert isinstance(report['api']['absolute_path_leaks'], int)
    assert isinstance(report['api']['formats'], list) and all(isinstance(x, str) for x in report['api']['formats'])
    assert isinstance(report['api']['catalog_sha256'], str) and len(report['api']['catalog_sha256']) == 64
    int(report['api']['catalog_sha256'], 16)
    assert isinstance(report['manifest']['declared_count'], int)
    for key in ('expected_names', 'missing_files', 'unexpected_files'):
        assert isinstance(report['manifest'][key], list)
        assert all(isinstance(x, str) for x in report['manifest'][key])
        assert report['manifest'][key] == sorted(report['manifest'][key])
    for mismatch in report['manifest']['mismatches']:
        assert set(mismatch) == {'name', 'fields'}
        assert mismatch['fields'] == sorted(mismatch['fields'], key=MANIFEST_FIELD_ORDER.index)
    for name, digest in report['manifest']['content_sha256'].items():
        assert isinstance(name, str)
        assert isinstance(digest, str) and len(digest) == 64
        int(digest, 16)
    assert isinstance(report['manifest']['passed'], bool)
    assert isinstance(report['policy']['passed'], bool)
    assert isinstance(report['policy']['accepted_names'], list)
    assert report['policy']['accepted_names'] == sorted(report['policy']['accepted_names'])
    for entry in report['policy']['quarantined']:
        assert set(entry) == {'name', 'reasons'}
        assert entry['reasons'] == sorted(entry['reasons'], key=REASON_ORDER.index)
    assert isinstance(report['policy']['risk_score'], int)
    assert isinstance(report['policy']['catalog_merkle_root'], str) and len(report['policy']['catalog_merkle_root']) == 64
    int(report['policy']['catalog_merkle_root'], 16)


@pytest.fixture(scope='session')
def hardened_report():
    """Run make report with poisoned yq and wrapped jq, then return the parsed base report."""
    run(['make', 'clean'])
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        fake = tmp_path / 'yq'
        fake.write_text('#!/bin/sh\necho "fake path yq should not be used" >&2\nexit 42\n')
        fake.chmod(0o755)
        real_jq = shutil.which('jq')
        assert real_jq, 'jq must be available in the verifier image'
        jq_log = tmp_path / 'jq.calls'
        jq_wrapper = tmp_path / 'jq'
        jq_wrapper.write_text(f'#!/bin/sh\necho "$@" >> "{jq_log}"\nexec "{real_jq}" "$@"\n')
        jq_wrapper.chmod(0o755)
        env = os.environ.copy()
        env['PATH'] = f'{tmp}:{env["PATH"]}'
        run(['make', 'report', f'PORT={free_port()}'], env=env, timeout=180)
        assert jq_log.exists(), 'make report must invoke jq at runtime'
        jq_calls = [line.strip() for line in jq_log.read_text().splitlines() if line.strip()]
        assert jq_calls, 'make report must invoke jq at runtime'
        joined = '\n'.join(jq_calls)
        assert any(token in joined for token in ('.status', '.debug', '.count', '.items', '.format')), 'jq should inspect named API JSON fields'
    assert REPORT.exists(), 'make report must create build/hardened-report.json'
    return json.loads(REPORT.read_text())


def assert_report_matches_current_state(report, *, should_pass=True):
    assert_exact_report_schema(report)
    expected_items = policy_expectations()['accepted_items']
    expected_manifest_report = expected_manifest()
    expected_policy = policy_expectations()
    assert report['security']['passed'] is should_pass
    assert report['manifest'] == expected_manifest_report
    assert report['policy']['passed'] is (not expected_policy['quarantined'])
    assert report['policy']['accepted_names'] == expected_policy['accepted_names']
    assert report['policy']['quarantined'] == expected_policy['quarantined']
    assert report['policy']['risk_score'] == expected_policy['risk_score']
    assert report['policy']['catalog_merkle_root'] == merkle_root(expected_items, content_hashes())
    assert report['api']['media_count'] == len(expected_items)
    assert report['api']['absolute_path_leaks'] == 0
    assert report['api']['formats'] == [item['format'] for item in expected_items]
    assert report['api']['catalog_sha256'] == compact_catalog_digest(expected_items)


def test_config_and_openapi_are_hardened():
    """Config disables insecure defaults, pins offline yq, declares policy, and OpenAPI describes auth."""
    config = yaml.safe_load(CONFIG.read_text())
    assert config['service']['debug'] is False
    assert config['service']['host'] in {'127.0.0.1', 'localhost'}
    assert '*' not in config['service'].get('cors_origins', [])
    assert ALLOWED_ORIGIN in config['service'].get('cors_origins', [])
    assert config['service']['api_key_header'] == API_KEY_HEADER
    assert config['service']['api_key'] == API_KEY
    assert config['service']['response_headers']['cache_control'] == 'no-store'
    assert config['service']['response_headers']['x_content_type_options'].lower() == 'nosniff'
    assert config['media']['include_absolute_paths'] is False
    policy = config['media']['policy']
    assert policy['max_pixels'] == 24
    assert policy['serve_only_manifest_valid'] is True
    assert set(policy['reason_weights']) == set(DEFAULT_WEIGHTS)
    manifest = config['media'].get('manifest', [])
    assert len(manifest) == 2
    assert sorted(entry['name'] for entry in manifest) == ['poster.jpg', 'shore.png']
    for entry in manifest:
        assert set(entry) == {'name', 'sha256', 'format', 'width', 'height', 'mode', 'signature'}
        assert len(entry['sha256']) == 64
        int(entry['sha256'], 16)
        assert entry['signature'] == manifest_signature(entry)
    yq_pin = config['build']['yq']
    assert yq_pin['version'] == PINNED_YQ_VERSION
    assert yq_pin['artifact'] == 'yq_linux_amd64'
    assert yq_pin['sha256'] == PINNED_YQ_SHA256
    assert yq_pin['source'] == 'vendor/yq_linux_amd64'
    assert not str(yq_pin.get('url', '')).startswith(('http://', 'https://'))
    openapi = yaml.safe_load((APP / 'openapi.yaml').read_text())
    assert openapi['servers'][0]['url'].startswith('http://127.0.0.1')
    assert openapi['info']['version'] != '0.1.0'
    schemes = openapi.get('components', {}).get('securitySchemes', {})
    assert schemes['ApiKeyAuth']['type'] == 'apiKey'
    assert schemes['ApiKeyAuth']['in'] == 'header'
    assert schemes['ApiKeyAuth']['name'] == API_KEY_HEADER
    assert {'ApiKeyAuth': []} in openapi['paths']['/media']['get'].get('security', [])


def test_makefile_and_perl_analyzer_use_verified_project_yq(hardened_report):
    """Makefile must use .tools/yq, reject PATH yq, and Perl must inspect YAML/JSON with real tools."""
    makefile = (APP / 'Makefile').read_text()
    assert 'bootstrap-yq' in makefile
    assert '.tools/yq' in makefile
    assert 'command -v yq' not in makefile
    assert 'YQ ?= $(shell' not in makefile
    assert '?= yq' not in makefile
    analyzer = (APP / 'scripts' / 'analyze.pl').read_text()
    assert 'Digest::SHA' in analyzer
    assert 'HTTP::Tiny' in analyzer or 'curl' in analyzer
    assert 'jq' in analyzer
    assert '/usr/bin/jq' not in analyzer
    assert '.status' in analyzer and '.count' in analyzer
    run(['perl', '-c', 'scripts/analyze.pl'])
    yq_path = APP / '.tools' / 'yq'
    assert yq_path.exists() and os.access(yq_path, os.X_OK)
    assert hashlib.sha256(yq_path.read_bytes()).hexdigest() == PINNED_YQ_SHA256
    version = run([str(yq_path), '--version']).stdout.strip()
    assert PINNED_YQ_VERSION in version


def test_bootstrap_rejects_tampered_bundled_yq_artifact():
    """bootstrap-yq must fail offline when the bundled yq artifact no longer matches the pin."""
    vendor = APP / 'vendor' / 'yq_linux_amd64'
    original = vendor.read_bytes()
    run(['make', 'clean'])
    try:
        vendor.write_bytes(original + b'corruption')
        proc = subprocess.run(['make', 'bootstrap-yq'], cwd=APP, text=True, capture_output=True, timeout=60)
        assert proc.returncode != 0
        assert 'checksum' in (proc.stdout + proc.stderr).lower() or 'sha' in (proc.stdout + proc.stderr).lower()
    finally:
        vendor.write_bytes(original)
        run(['make', 'clean'])


def test_hardened_report_was_built_from_yq_jq_manifest_policy_and_live_api(hardened_report):
    """Base report must combine live API data, manifest validation, policy classification, and Merkle digest."""
    report = hardened_report
    assert report['security']['passed'] is True
    assert report['yq']['version'] == PINNED_YQ_VERSION
    assert report['yq']['sha256'] == PINNED_YQ_SHA256
    assert Path(report['yq']['path']).resolve() == (APP / '.tools' / 'yq').resolve()
    assert PINNED_YQ_VERSION in report['yq']['version_output']
    assert report['config']['debug'] is False
    assert report['config']['host'] in {'127.0.0.1', 'localhost'}
    assert report['config']['cors_wildcard'] is False
    assert report['config']['leaks_absolute_paths'] is False
    assert report['api']['health_status'] == 'ok'
    assert report['api']['debug'] is False
    assert report['api']['auth_required'] is True
    assert report['api']['unauthorized_status'] == 401
    assert_report_matches_current_state(report, should_pass=True)


def test_report_reflects_current_fixture_and_manifest_set(hardened_report):
    """A valid new fixture and signed manifest entry must update count, duplicate formats, and Merkle root."""
    original_config = CONFIG.read_text()
    extra = APP / 'fixtures' / 'dynamic-extra.png'
    Image.new('RGB', (3, 2)).save(extra)
    try:
        config = yaml.safe_load(original_config)
        config['media']['manifest'].append(manifest_entry_for(extra))
        CONFIG.write_text(yaml.safe_dump(config, sort_keys=False))
        run(['make', 'report', f'PORT={free_port()}'], timeout=180)
        report = json.loads(REPORT.read_text())
        assert_report_matches_current_state(report, should_pass=True)
        assert report['api']['media_count'] == 3
        assert report['api']['formats'] == ['PNG', 'JPEG', 'PNG'] or sorted(report['api']['formats']) == ['JPEG', 'PNG', 'PNG']
        assert report['policy']['quarantined'] == []
    finally:
        CONFIG.write_text(original_config)
        extra.unlink(missing_ok=True)
        run(['make', 'clean'])
        run(['make', 'report', f'PORT={free_port()}'], timeout=180)


def test_unexpected_fixture_is_quarantined_and_excluded_from_api(hardened_report):
    """An allowed image not listed in the manifest must be reported, scored, and excluded from /media."""
    original_config = CONFIG.read_text()
    rogue = APP / 'fixtures' / 'rogue.png'
    Image.new('RGB', (2, 2)).save(rogue)
    try:
        report = run_report_expect_failure()
        assert_report_matches_current_state(report, should_pass=False)
        assert report['manifest']['unexpected_files'] == ['rogue.png']
        assert report['policy']['quarantined'] == [{'name': 'rogue.png', 'reasons': ['missing_manifest']}]
        assert report['policy']['risk_score'] == DEFAULT_WEIGHTS['missing_manifest']
        assert 'rogue.png' not in report['policy']['accepted_names']
        assert report['api']['media_count'] == 2
    finally:
        CONFIG.write_text(original_config)
        rogue.unlink(missing_ok=True)
        run(['make', 'clean'])
        run(['make', 'report', f'PORT={free_port()}'], timeout=180)


def test_manifest_valid_oversized_fixture_triggers_pixels_quarantine(hardened_report):
    """A manifest-valid image over max_pixels must be quarantined only for the pixels policy reason."""
    original_config = CONFIG.read_text()
    oversized = APP / 'fixtures' / 'oversized.png'
    Image.new('RGB', (5, 5)).save(oversized)
    try:
        config = yaml.safe_load(original_config)
        config['media']['manifest'].append(manifest_entry_for(oversized))
        CONFIG.write_text(yaml.safe_dump(config, sort_keys=False))
        report = run_report_expect_failure()
        assert_report_matches_current_state(report, should_pass=False)
        assert report['manifest']['passed'] is True
        assert report['policy']['quarantined'] == [{'name': 'oversized.png', 'reasons': ['pixels']}]
        assert report['policy']['risk_score'] == DEFAULT_WEIGHTS['pixels']
        assert 'oversized.png' not in report['policy']['accepted_names']
        assert report['api']['media_count'] == 2
    finally:
        CONFIG.write_text(original_config)
        oversized.unlink(missing_ok=True)
        run(['make', 'clean'])
        run(['make', 'report', f'PORT={free_port()}'], timeout=180)


def test_manifest_name_collision_quarantines_both_colliding_files(hardened_report):
    """Two valid manifest entries with the same normalized stem must both be quarantined by policy."""
    original_config = CONFIG.read_text()
    collision = APP / 'fixtures' / 'SHORE.PNG'
    shutil.copyfile(APP / 'fixtures' / 'shore.png', collision)
    try:
        config = yaml.safe_load(original_config)
        config['media']['manifest'].append(manifest_entry_for(collision))
        CONFIG.write_text(yaml.safe_dump(config, sort_keys=False))
        report = run_report_expect_failure()
        assert_exact_report_schema(report)
        assert report['manifest']['passed'] is True
        assert report['security']['passed'] is False
        assert report['policy']['passed'] is False
        assert report['policy']['quarantined'] == [
            {'name': 'SHORE.PNG', 'reasons': ['name_collision']},
            {'name': 'shore.png', 'reasons': ['name_collision']},
        ]
        assert report['policy']['risk_score'] == 2 * DEFAULT_WEIGHTS['name_collision']
        assert report['policy']['accepted_names'] == ['poster.jpg']
        assert report['api']['media_count'] == 1
    finally:
        CONFIG.write_text(original_config)
        collision.unlink(missing_ok=True)
        run(['make', 'clean'])
        run(['make', 'report', f'PORT={free_port()}'], timeout=180)


def test_collision_id_normalizes_punctuation_runs_and_trimming(hardened_report):
    """Collision ids must use full normalization, not just case folding."""
    original_config = CONFIG.read_text()
    first = APP / 'fixtures' / 'my--file (1).png'
    second = APP / 'fixtures' / 'my_file_1.png'
    Image.new('RGB', (2, 2)).save(first)
    Image.new('RGB', (2, 2)).save(second)
    try:
        assert collision_id(first.name) == collision_id(second.name) == 'my-file-1'
        config = yaml.safe_load(original_config)
        config['media']['manifest'].append(manifest_entry_for(first))
        config['media']['manifest'].append(manifest_entry_for(second))
        CONFIG.write_text(yaml.safe_dump(config, sort_keys=False))
        report = run_report_expect_failure()
        assert_exact_report_schema(report)
        assert report['manifest']['passed'] is True
        assert report['security']['passed'] is False
        assert report['policy']['quarantined'] == [
            {'name': 'my--file (1).png', 'reasons': ['name_collision']},
            {'name': 'my_file_1.png', 'reasons': ['name_collision']},
        ]
        assert report['policy']['risk_score'] == 2 * DEFAULT_WEIGHTS['name_collision']
        assert report['policy']['accepted_names'] == ['poster.jpg', 'shore.png']
        assert report['api']['media_count'] == 2
    finally:
        CONFIG.write_text(original_config)
        first.unlink(missing_ok=True)
        second.unlink(missing_ok=True)
        run(['make', 'clean'])
        run(['make', 'report', f'PORT={free_port()}'], timeout=180)



def test_combined_policy_reasons_are_ordered_and_weighted(hardened_report):
    """Combined metadata, pixel, and collision failures must preserve ordered reasons and risk scoring."""
    first = APP / 'fixtures' / 'combo!! 1.png'
    second = APP / 'fixtures' / 'combo_1.png'
    original_config = CONFIG.read_text()
    try:
        Image.new('RGB', (5, 5)).save(first)
        Image.new('RGB', (2, 2)).save(second)
        config = yaml.safe_load(original_config)
        bad_width = manifest_entry_for(first)
        bad_width['width'] = 4
        bad_width['signature'] = manifest_signature(bad_width)
        config['media']['manifest'].append(bad_width)
        config['media']['manifest'].append(manifest_entry_for(second))
        CONFIG.write_text(yaml.safe_dump(config, sort_keys=False))
        report = run_report_expect_failure()
        assert_exact_report_schema(report)
        assert report['manifest']['mismatches'] == [{'name': 'combo!! 1.png', 'fields': ['width']}]
        assert report['policy']['quarantined'] == [
            {'name': 'combo!! 1.png', 'reasons': ['width', 'pixels', 'name_collision']},
            {'name': 'combo_1.png', 'reasons': ['name_collision']},
        ]
        assert report['policy']['risk_score'] == DEFAULT_WEIGHTS['width'] + DEFAULT_WEIGHTS['pixels'] + 2 * DEFAULT_WEIGHTS['name_collision']
        assert report['policy']['accepted_names'] == ['poster.jpg', 'shore.png']
        assert report['api']['media_count'] == 2
        assert report['security']['passed'] is False
    finally:
        CONFIG.write_text(original_config)
        first.unlink(missing_ok=True)
        second.unlink(missing_ok=True)
        run(['make', 'clean'])
        run(['make', 'report', f'PORT={free_port()}'], timeout=180)

def test_report_detects_manifest_sha_drift_after_writing_report(hardened_report):
    """A bad manifest SHA must be reported in manifest and policy sections after report write."""
    original_config = CONFIG.read_text()
    config = yaml.safe_load(original_config)
    config['media']['manifest'][0]['sha256'] = '0' * 64
    CONFIG.write_text(yaml.safe_dump(config, sort_keys=False))
    try:
        report = run_report_expect_failure()
        assert_report_matches_current_state(report, should_pass=False)
        assert report['manifest']['mismatches'] == [{'name': 'poster.jpg', 'fields': ['sha256', 'signature']}]
        assert {'name': 'poster.jpg', 'reasons': ['sha256', 'signature']} in report['policy']['quarantined']
        assert report['api']['media_count'] == 1
    finally:
        CONFIG.write_text(original_config)
        run(['make', 'clean'])
        run(['make', 'report', f'PORT={free_port()}'], timeout=180)


def test_report_detects_manifest_signature_drift_after_writing_report(hardened_report):
    """A bad manifest signature alone must be reported without inventing SHA drift."""
    original_config = CONFIG.read_text()
    config = yaml.safe_load(original_config)
    config['media']['manifest'][1]['signature'] = 'f' * 64
    CONFIG.write_text(yaml.safe_dump(config, sort_keys=False))
    try:
        report = run_report_expect_failure()
        assert_report_matches_current_state(report, should_pass=False)
        assert report['manifest']['mismatches'] == [{'name': 'shore.png', 'fields': ['signature']}]
        assert {'name': 'shore.png', 'reasons': ['signature']} in report['policy']['quarantined']
        assert report['api']['media_count'] == 1
    finally:
        CONFIG.write_text(original_config)
        run(['make', 'clean'])
        run(['make', 'report', f'PORT={free_port()}'], timeout=180)


def test_report_detects_manifest_metadata_field_drift_after_writing_report(hardened_report):
    """A manifest metadata drift with a valid signature must report only that metadata field."""
    original_config = CONFIG.read_text()
    config = yaml.safe_load(original_config)
    entry = config['media']['manifest'][0]
    entry['width'] = int(entry['width']) + 1
    entry['signature'] = manifest_signature(entry)
    CONFIG.write_text(yaml.safe_dump(config, sort_keys=False))
    try:
        report = run_report_expect_failure()
        assert_report_matches_current_state(report, should_pass=False)
        assert report['manifest']['mismatches'] == [{'name': 'poster.jpg', 'fields': ['width']}]
        assert {'name': 'poster.jpg', 'reasons': ['width']} in report['policy']['quarantined']
        assert report['manifest']['passed'] is False
        assert report['policy']['passed'] is False
        assert report['security']['passed'] is False
        assert report['api']['media_count'] == 1
    finally:
        CONFIG.write_text(original_config)
        run(['make', 'clean'])
        run(['make', 'report', f'PORT={free_port()}'], timeout=180)


def test_live_api_secure_headers_auth_cors_and_policy_payload():
    """Live Flask responses enforce headers/auth/CORS and serve only policy-accepted media."""
    port = free_port()
    env = os.environ.copy()
    env['MEDIA_CONFIG'] = str(CONFIG)
    env['PORT'] = str(port)
    proc = subprocess.Popen([sys.executable, 'api/app.py'], cwd=APP, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        health = wait_for(f'http://127.0.0.1:{port}/health')
        assert health.json()['debug'] is False
        assert health.headers.get('Cache-Control') == 'no-store'
        assert health.headers.get('X-Content-Type-Options', '').lower() == 'nosniff'
        missing_key = requests.get(f'http://127.0.0.1:{port}/media', headers={'Origin': ALLOWED_ORIGIN}, timeout=5)
        assert missing_key.status_code == 401
        assert missing_key.headers.get('Access-Control-Allow-Origin') == ALLOWED_ORIGIN
        blocked = requests.get(f'http://127.0.0.1:{port}/media', headers={'Origin': 'https://evil.example', API_KEY_HEADER: API_KEY}, timeout=5)
        assert blocked.status_code == 200
        assert blocked.headers.get('Access-Control-Allow-Origin') not in {'*', 'https://evil.example'}
        allowed = requests.get(f'http://127.0.0.1:{port}/media', headers={'Origin': ALLOWED_ORIGIN, API_KEY_HEADER: API_KEY}, timeout=5)
        assert allowed.status_code == 200
        assert allowed.headers.get('Access-Control-Allow-Origin') == ALLOWED_ORIGIN
        payload = allowed.json()
        expected_items = policy_expectations()['accepted_items']
        assert payload['count'] == len(expected_items) == 2
        assert payload['items'] == expected_items
        for item in payload['items']:
            assert set(item) == set(ITEM_KEYS)
            assert item['width'] > 0 and item['height'] > 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
