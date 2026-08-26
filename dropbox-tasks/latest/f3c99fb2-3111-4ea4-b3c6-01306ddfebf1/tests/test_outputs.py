from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path('/app/environment')
SERVICE = ROOT / 'engine'
DOSSIER = ROOT / 'dossier' / 'incident-dossier.md'
FIXTURES = ROOT / 'fixtures'
NODE_PATH = str(SERVICE / 'node_modules')


def node(script: str, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    env = {**os.environ, 'NODE_PATH': NODE_PATH}
    return subprocess.run(['node', '-e', script, *map(str, args)], text=True, capture_output=True, env=env, check=check, timeout=90)


def make_case(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    repo = tmp_path / 'media-api'
    fixtures = tmp_path / 'fixtures'
    dossier = tmp_path / 'incident-dossier.md'
    output = tmp_path / 'out'
    shutil.copytree(SERVICE, repo, ignore=shutil.ignore_patterns('node_modules'))
    shutil.copytree(FIXTURES, fixtures)
    shutil.copy2(DOSSIER, dossier)
    return repo, fixtures, dossier, output


RUN = """
const { hardenMediaInferenceDefaults } = require(process.argv[1]);
hardenMediaInferenceDefaults(process.argv[2], process.argv[3], process.argv[4], process.argv[5])
  .then((value) => process.stdout.write(JSON.stringify(value)))
  .catch((error) => { process.stderr.write(error.stack || error.message); process.exit(7); });
"""


def run(repo: Path, dossier: Path, fixtures: Path, output: Path, check: bool = True):
    return node(RUN, repo / 'index.js', repo, dossier, fixtures, output, check=check)


def read_config(repo: Path) -> dict:
    return json.loads(node("process.stdout.write(JSON.stringify(require(process.argv[1])))", repo / 'config' / 'inference.js').stdout)


def test_r01_primary_record_export(tmp_path: Path):
    """Primary record export must produce mutually consistent observations."""
    repo, fixtures, dossier, out = make_case(tmp_path)
    policy = json.loads(run(repo, dossier, fixtures, out).stdout)
    assert policy == {
        'debugInferenceEnabled': False,
        'corsAllowedOrigins': ['https://console.media.example', 'https://review.media.example'],
        'maxUploadBytes': 12582912,
        'telemetryRedactionEnabled': True,
        'telemetryRedactedFields': ['request.imagePath', 'request.originalFilename', 'request.ipAddress', 'request.userAgent'],
        'moderationThresholds': {'safe': 0.92, 'suggestive': 0.73, 'explicit': 0.86},
    }
    assert read_config(repo)['cors']['origin'] == policy['corsAllowedOrigins']
    assert json.loads((out / 'deployment-policy.json').read_text()) == policy
    terraform = json.loads((out / 'terraform-defaults.json').read_text())
    assert terraform['telemetry_redacted_fields'] == policy['telemetryRedactedFields']
    decisions = json.loads((out / 'fixture-decisions.json').read_text())['decisions']
    assert [item['id'] for item in decisions] == [f'fixture-{n:02d}' for n in range(1, 9)]
    assert all(item['flagged'] == (item['confidence'] >= policy['moderationThresholds'][item['label']]) for item in decisions)


def test_r02_convergent_mutation(tmp_path: Path):
    """Repeated reconciliation preserves unrelated source material byte-for-byte."""
    repo, fixtures, dossier, out = make_case(tmp_path)
    config = repo / 'config' / 'inference.js'
    config.write_text(config.read_text().replace('"port": 3000,', '"port": 3000,\n    "retentionDays": 45,'))
    tfvars = repo / 'terraform' / 'production.tfvars'
    tfvars.write_text(tfvars.read_text() + '\nrelease_channel = "blue"\n')
    run(repo, dossier, fixtures, out)
    snapshot = {path.name: path.read_bytes() for path in [config, tfvars, *(out / name for name in ['deployment-policy.json', 'terraform-defaults.json', 'fixture-decisions.json'])]}
    run(repo, dossier, fixtures, out)
    assert snapshot == {path.name: path.read_bytes() for path in [config, tfvars, *(out / name for name in ['deployment-policy.json', 'terraform-defaults.json', 'fixture-decisions.json'])]}
    assert read_config(repo)['service']['retentionDays'] == 45
    assert 'release_channel = "blue"' in tfvars.read_text()
    assert tfvars.read_text().count('max_upload_bytes') == 1


def test_r03_rejected_authority_is_atomic(tmp_path: Path):
    """Conflicting authority must reject without any partial mutable-state change."""
    repo, fixtures, dossier, _ = make_case(tmp_path)
    out = tmp_path
    (out / 'sentinel.json').write_text('{"keep":true}\n')
    bad = tmp_path / 'bad.md'
    bad.write_text(dossier.read_text() + '''
Record: CAB-2099-001
Recorded-At: 2026-06-19T00:00:00Z
Scope: production
State: ratified
Approvals: security, sre
CORS-Origins: https://other.media.example
''')
    before = (repo / 'config' / 'inference.js').read_bytes(), (repo / 'terraform' / 'production.tfvars').read_bytes(), (out / 'sentinel.json').read_bytes()
    result = run(repo, bad, fixtures, out, check=False)
    assert result.returncode != 0
    assert before == ((repo / 'config' / 'inference.js').read_bytes(), (repo / 'terraform' / 'production.tfvars').read_bytes(), (out / 'sentinel.json').read_bytes())


def test_r04_indexed_collection(tmp_path: Path):
    """Fixture observations follow explicit indexes and reject duplicate positions."""
    repo, fixtures, dossier, out = make_case(tmp_path)
    manifest = json.loads((fixtures / 'manifest.json').read_text())
    manifest['fixtures'][0], manifest['fixtures'][7] = manifest['fixtures'][7], manifest['fixtures'][0]
    (fixtures / 'manifest.json').write_text(json.dumps(manifest))
    run(repo, dossier, fixtures, out)
    decisions = json.loads((out / 'fixture-decisions.json').read_text())['decisions']
    assert [entry['id'] for entry in decisions] == [f'fixture-{n:02d}' for n in range(1, 9)]
    manifest['fixtures'][1]['index'] = manifest['fixtures'][0]['index']
    (fixtures / 'manifest.json').write_text(json.dumps(manifest))
    assert run(repo, dossier, fixtures, out, check=False).returncode != 0


def test_r05_refreshes_new_inputs(tmp_path: Path):
    """A second call in one process observes a newly supplied authority export."""
    repo, fixtures, dossier, out = make_case(tmp_path)
    next_dossier = tmp_path / 'next.md'
    next_dossier.write_text(dossier.read_text() + '''
Record: CAB-2026-099
Recorded-At: 2026-06-19T10:00:00Z
Scope: production
State: ratified
Approvals: security, sre
Supersedes: CAB-2026-071
CORS-Origins: https://review.media.example, https://console.media.example
Max-Upload-Bytes: 8388608
''')
    script = """
    const h = require(process.argv[1]).hardenMediaInferenceDefaults;
    (async () => { await h(process.argv[2], process.argv[3], process.argv[4], process.argv[5]); await h(process.argv[2], process.argv[6], process.argv[4], process.argv[5]); })()
      .catch((error) => { console.error(error.stack || error.message); process.exit(9); });
    """
    node(script, repo / 'index.js', repo, dossier, fixtures, out, next_dossier)
    policy = json.loads((out / 'deployment-policy.json').read_text())
    assert policy['maxUploadBytes'] == 8388608
    assert policy['corsAllowedOrigins'] == ['https://review.media.example', 'https://console.media.example']


def test_r06_public_surface(tmp_path: Path):
    """The hardened HTTP surface excludes diagnostics and redacts nested telemetry."""
    repo, fixtures, dossier, out = make_case(tmp_path)
    run(repo, dossier, fixtures, out)
    script = """
    const { createApp } = require(process.argv[1]);
    const config = require(process.argv[2]);
    const { redactTelemetry } = require(process.argv[3]);
    const app = createApp(config, () => {});
    const routes = app._router.stack.filter((layer) => layer.route).map((layer) => layer.route.path);
    const redacted = redactTelemetry({request:{imagePath:'a', originalFilename:'b', ipAddress:'c', userAgent:'d'}}, config.telemetryRedactedFields);
    process.stdout.write(JSON.stringify({routes, redacted}));
    """
    result = json.loads(node(script, repo / 'server.js', repo / 'config' / 'inference.js', repo / 'lib' / 'telemetry' / 'redact.js').stdout)
    assert '/health' in result['routes'] and '/moderate' in result['routes'] and '/debug/infer' not in result['routes']
    assert set(result['redacted']['request'].values()) == {'[REDACTED]'}
