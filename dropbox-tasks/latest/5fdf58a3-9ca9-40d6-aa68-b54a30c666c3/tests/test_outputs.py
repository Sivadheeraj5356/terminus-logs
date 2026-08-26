import csv
import json
import os
import subprocess
import time
import datetime
import hmac
import hashlib
import random
import secrets
import shlex
from pathlib import Path
from tempfile import TemporaryDirectory

# Test audit trail and HMAC signatures

AUDIT_SEED = 42

def _write_ledger(ledger_path, rows):
    """Write CSV ledger."""
    with open(ledger_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['service', 'hostname', 'sans', 'key_algorithm', 'rotate_before_days'])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

def _sample_rows():
    """Generate sample ledger rows."""
    return [
        {
            'service': 'worker',
            'hostname': 'worker.internal.example',
            'sans': 'DNS:worker.internal.example,DNS:worker',
            'key_algorithm': 'rsa',
            'rotate_before_days': '30',
        },
        {
            'service': 'api',
            'hostname': 'api.internal.example',
            'sans': 'DNS:api.internal.example,DNS:api',
            'key_algorithm': 'ec',
            'rotate_before_days': '14',
        },
    ]

def _run(cmd, cwd=None):
    """Run a shell command."""
    res = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    return res

def _run_worker(ledger, pki, audit_seed=AUDIT_SEED, extra_env=None):
    """Run the worker."""
    cmd = f'node /app/src/worker.js --ledger {ledger} --pki-dir {pki}'
    env = dict(AUDIT_SEED=str(audit_seed))
    if extra_env:
        env.update(extra_env)
    env_cmd = ' '.join(f'{k}={shlex.quote(str(v))}' for k, v in env.items())
    cmd = f'{env_cmd} {cmd}'
    res = _run(cmd)
    return res

def _cert_not_after(cert_path):
    """Extract certificate NotAfter date."""
    res = _run(f"openssl x509 -in {cert_path} -noout -text")
    for line in res.stdout.split('\n'):
        if 'Not After' in line:
            date_str = line.split(': ')[1]
            return datetime.datetime.strptime(date_str, '%b %d %H:%M:%S %Y %Z')
    return None


def _cert_not_before(cert_path):
    """Extract certificate NotBefore date."""
    res = _run(f"openssl x509 -in {cert_path} -noout -text")
    for line in res.stdout.split('\n'):
        if 'Not Before' in line:
            date_str = line.split(': ', 1)[1]
            return datetime.datetime.strptime(date_str, '%b %d %H:%M:%S %Y %Z')
    return None


def _cert_validity_seconds(cert_path):
    """Return validity duration in seconds from NotBefore to NotAfter."""
    nb = _cert_not_before(cert_path)
    na = _cert_not_after(cert_path)
    if nb is None or na is None:
        return None
    return int((na - nb).total_seconds())


def _int_key_hash(path):
    """Compute intermediate key fingerprint same way worker does."""
    pubkey = _run(f"openssl pkey -in {path} -pubout -outform PEM")
    assert pubkey.returncode == 0, pubkey.stderr
    return hashlib.sha256(pubkey.stdout.encode()).hexdigest()

def _cert_serial(cert_path):
    """Extract certificate serial number as hex."""
    res = _run(f"openssl x509 -in {cert_path} -noout -serial")
    serial_str = res.stdout.strip().split('=')[1]
    return serial_str.lower()

def _mode(path):
    """Get file permissions."""
    return oct(os.stat(path).st_mode)[-3:]

def _derive_daily_audit_key(audit_secret_seed, day_epoch):
    """Derive daily HMAC-SHA256 key from seed and epoch day (matching oracle)."""
    import hashlib
    # First, derive AUDIT_SECRET from seed
    audit_secret = hashlib.sha256(f'cert-audit-{audit_secret_seed}'.encode()).digest()
    # Then, derive daily key from AUDIT_SECRET and dayEpoch
    return hmac.new(audit_secret, str(day_epoch).encode(), hashlib.sha256).digest()

def _verify_hmac_signature(entry, daily_key):
    """Verify HMAC-SHA256 signature of an audit entry."""
    canonical_data = _canonical_audit_payload(entry)
    canonical_json = json.dumps(canonical_data, sort_keys=True, separators=(',', ':'))
    expected_sig = hmac.new(daily_key, canonical_json.encode(), hashlib.sha256).hexdigest()
    return entry['audit_signature'] == expected_sig

def _canonical_audit_payload(entry):
    """Canonical audit payload used for hash/signature checks."""
    return {
        'service': entry['service'],
        'action': entry['action'],
        'key_algorithm': entry['key_algorithm'],
        'expires_at': entry['expires_at'],
        'timestamp': entry['timestamp'],
        'prev_hash': entry.get('prev_hash', ''),
    }

def _entry_hash_from_payload(entry):
    """Compute SHA-256 hash for canonical audit payload."""
    canonical_json = json.dumps(_canonical_audit_payload(entry), sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical_json.encode()).hexdigest()

def _derive_manifest_secret(service, key_history_path):
    """Derive per-service manifest HMAC key from first intermediate key hash."""
    lines = [ln.strip() for ln in Path(key_history_path).read_text().splitlines() if ln.strip()]
    anchor = lines[0] if lines else 'bootstrap'
    return hashlib.sha256(f'manifest:{service}:{anchor}'.encode()).digest()

def _canonical_manifest_entry(entry):
    return {
        'action': entry['action'],
        'expires_at': entry['expires_at'],
        'issued_at': entry['issued_at'],
        'prev_entry_hash': entry.get('prev_entry_hash', ''),
        'public_key_sha256': entry['public_key_sha256'],
        'serial': entry['serial'],
    }

def _manifest_entry_hash(entry):
    canonical_json = json.dumps(_canonical_manifest_entry(entry), sort_keys=False, separators=(',', ':'))
    return hashlib.sha256(canonical_json.encode()).hexdigest()

def _manifest_entry_sig(entry, manifest_secret):
    canonical_json = json.dumps(_canonical_manifest_entry(entry), sort_keys=False, separators=(',', ':'))
    return hmac.new(manifest_secret, canonical_json.encode(), hashlib.sha256).hexdigest()

def _verify_manifest_chain(service_dir, service_name):
    manifest_path = service_dir / 'manifest.json'
    key_history = service_dir / '.int_key_hashes'
    manifest = json.loads(manifest_path.read_text())
    assert manifest.get('service') == service_name
    secret = _derive_manifest_secret(service_name, key_history)

    expected_prev = ''
    last_issued_at = ''
    for entry in manifest['issued_certificates']:
        for field in ('serial', 'issued_at', 'expires_at', 'action', 'public_key_sha256', 'prev_entry_hash', 'entry_hash', 'entry_sig'):
            assert field in entry, f'manifest entry missing field: {field}'

        assert entry['issued_at'] >= last_issued_at, 'manifest entries not ordered by issued_at'
        last_issued_at = entry['issued_at']

        assert entry['prev_entry_hash'] == expected_prev, 'manifest prev_entry_hash chain broken'
        assert entry['entry_hash'] == _manifest_entry_hash(entry), 'manifest entry_hash mismatch'
        assert entry['entry_sig'] == _manifest_entry_sig(entry, secret), 'manifest entry_sig mismatch'
        expected_prev = entry['entry_hash']

def _compute_pubkey_sha256(cert_path):
    """Extract public key from certificate and compute SHA256 hash (hex)."""
    res = _run(f"openssl x509 -in {cert_path} -pubkey -noout")
    pubkey_pem = res.stdout
    pubkey_hash = hashlib.sha256(pubkey_pem.encode()).hexdigest()
    return pubkey_hash

# =========================
# TESTS
# =========================

def test_files_exist():
    """Verify required files exist."""
    assert Path('/app/src/worker.js').exists(), 'worker.js missing'
    assert Path('/app/data/services.csv').exists(), 'ledger missing'
    assert Path('/app/package.json').exists(), 'package.json missing'

def test_codebase_smoke_script_passes():
    """Run smoke tests."""
    res = _run('bash /app/checks/smoke.sh')
    assert res.returncode == 0, f'smoke.sh failed: {res.stderr}'

def test_codebase_format_script_passes():
    """Run format checks."""
    res = _run('bash /app/checks/format.sh')
    assert res.returncode == 0, f'format.sh failed: {res.stderr}'

def test_multi_tier_pki_created():
    """Verify two-tier PKI structure with certificate chain validation."""
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ledger = tmp_path / 'services.csv'
        pki = tmp_path / 'pki'

        _write_ledger(ledger, _sample_rows())
        
        # First run: create intermediates (will be staged)
        res = _run_worker(ledger, pki)
        assert res.returncode == 0, f'Worker failed: {res.stderr}'

        # Verify root CA exists and is self-signed
        root_cert = pki / 'ca' / 'ca.crt.pem'
        assert root_cert.exists(), 'Root CA missing'
        root_text = _run(f'openssl x509 -in {root_cert} -noout -text').stdout
        assert 'CN' in root_text and 'openssl-ca-root' in root_text, 'Root CA CN incorrect'

        # Verify service intermediates exist and are signed by root
        for svc_name in ['worker', 'api']:
            int_cert = pki / 'services' / svc_name / 'int.crt.pem'
            assert int_cert.exists(), f'Intermediate for {svc_name} missing'

            validity_seconds = _cert_validity_seconds(int_cert)
            assert validity_seconds is not None, f'Could not read validity for {svc_name} intermediate'
            expected = 365 * 24 * 3600
            assert abs(validity_seconds - expected) <= 60, (
                f'Intermediate validity must be 365 days (within 60s), got {validity_seconds} seconds'
            )

            int_text = _run(f'openssl x509 -in {int_cert} -noout -text').stdout
            assert svc_name in int_text and 'int' in int_text.lower(), f'Intermediate CN incorrect for {svc_name}'
            assert 'CA:TRUE' in int_text, f'CA:TRUE extension missing for {svc_name} intermediate'

            # Verify intermediate signed by root (chain validation)
            verify_res = _run(f'openssl verify -CAfile {root_cert} {int_cert}')
            assert verify_res.returncode == 0, f'Intermediate {svc_name} not signed by root'

        # Age intermediates to enable cert issuance
        old_time = int(time.time()) - (8 * 24 * 60 * 60)
        for svc_name in ['worker', 'api']:
            created_at_file = pki / 'services' / svc_name / 'int_created_at'
            created_at_file.write_text(str(old_time))

        # Second run: issue service certificates
        res = _run_worker(ledger, pki)
        assert res.returncode == 0

        # Verify service certificates are signed by their intermediate (not root)
        for svc_name in ['worker', 'api']:
            cert = pki / 'services' / svc_name / 'cert.pem'
            int_cert = pki / 'services' / svc_name / 'int.crt.pem'
            assert cert.exists(), f'Service cert for {svc_name} missing'

            # Extract issuer from service cert and verify it matches intermediate CN
            cert_text = _run(f'openssl x509 -in {cert} -noout -text').stdout
            int_text = _run(f'openssl x509 -in {int_cert} -noout -text').stdout
            
            # Check that service cert issuer contains the intermediate's CN
            assert svc_name in cert_text and 'Issuer' in cert_text, f'Service cert {svc_name} issuer check failed'
            assert svc_name in int_text and 'Subject' in int_text, f'Intermediate {svc_name} subject check failed'
            
            # Verify SANs are present in service certificate
            san_text = _run(f'openssl x509 -in {cert} -noout -ext subjectAltName').stdout
            if svc_name == 'worker':
                assert 'worker.internal.example' in san_text or 'DNS:worker' in san_text, f'SANs missing for {svc_name}'
            elif svc_name == 'api':
                assert 'api.internal.example' in san_text or 'DNS:api' in san_text, f'SANs missing for {svc_name}'

def test_staging_period_enforced():
    """Verify 7-day staging period before cert issuance."""
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ledger = tmp_path / 'services.csv'
        pki = tmp_path / 'pki'

        _write_ledger(ledger, _sample_rows())

        # First run: intermediates are new, should return action="staged"
        res = _run_worker(ledger, pki)
        assert res.returncode == 0
        body = json.loads(res.stdout)
        assert body['status'] == 'ok'

        # All entries should be staged initially
        for entry in body['processed']:
            assert entry['action'] == 'staged', f"Expected staged, got {entry['action']}"
            assert 'serial' in entry
            assert 'cert_path' not in entry
            # Verify staged_at is present and valid ISO-8601 UTC
            assert 'staged_at' in entry, 'staged_at missing from staged entry'
            try:
                datetime.datetime.fromisoformat(entry['staged_at'].replace('Z', '+00:00'))
            except ValueError:
                raise AssertionError(f"staged_at not valid ISO-8601: {entry['staged_at']}")

        # Simulate 8 days passing by modifying int_created_at
        old_time = int(time.time()) - (8 * 24 * 60 * 60)
        for svc_name in ['worker', 'api']:
            created_at_file = pki / 'services' / svc_name / 'int_created_at'
            created_at_file.write_text(str(old_time))

        # Second run: intermediates are old enough, should issue
        res = _run_worker(ledger, pki)
        assert res.returncode == 0
        body = json.loads(res.stdout)
        assert body['status'] == 'ok'

        # All entries should now be issued
        for entry in body['processed']:
            assert entry['action'] == 'issued', f"Expected issued after 8 days, got {entry['action']}"
            assert 'cert_path' in entry
            assert 'key_path' in entry
            # Verify key_algorithm is present in output
            assert 'key_algorithm' in entry, 'key_algorithm missing from issued entry'
            assert entry['key_algorithm'] in ('rsa', 'ec'), f"Invalid key_algorithm: {entry['key_algorithm']}"

def test_algorithm_lock_in():
    """Verify algorithm immutability after first issuance."""
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ledger = tmp_path / 'services.csv'
        pki = tmp_path / 'pki'

        _write_ledger(ledger, _sample_rows())

        # First run: all staged (intermediates too new)
        res = _run_worker(ledger, pki)
        assert res.returncode == 0

        # Age intermediates
        old_time = int(time.time()) - (8 * 24 * 60 * 60)
        for svc_name in ['worker', 'api']:
            created_at_file = pki / 'services' / svc_name / 'int_created_at'
            created_at_file.write_text(str(old_time))

        # Second run: issue certs with initial algorithm
        res = _run_worker(ledger, pki)
        assert res.returncode == 0

        # Third run: change algorithm in ledger
        modified_rows = [
            {
                'service': 'api',
                'hostname': 'api.internal.example',
                'sans': 'DNS:api.internal.example,DNS:api',
                'key_algorithm': 'rsa',  # Changed from ec
                'rotate_before_days': '14',
            },
            {
                'service': 'worker',
                'hostname': 'worker.internal.example',
                'sans': 'DNS:worker.internal.example,DNS:worker',
                'key_algorithm': 'ec',  # Changed from rsa
                'rotate_before_days': '30',
            },
        ]
        _write_ledger(ledger, modified_rows)

        res = _run_worker(ledger, pki)
        assert res.returncode != 0, 'Should reject algorithm change'
        body = json.loads(res.stdout)
        assert body['code'] == 'algorithm_mismatch'

def test_expires_at_matches_certificate():
    """Verify expires_at matches certificate NotAfter exactly."""
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ledger = tmp_path / 'services.csv'
        pki = tmp_path / 'pki'

        _write_ledger(ledger, _sample_rows())

        # Age intermediates immediately
        old_time = int(time.time()) - (8 * 24 * 60 * 60)
        _run_worker(ledger, pki)
        for svc_name in ['worker', 'api']:
            created_at_file = pki / 'services' / svc_name / 'int_created_at'
            created_at_file.write_text(str(old_time))

        # Issue certs
        res = _run_worker(ledger, pki)
        assert res.returncode == 0
        body = json.loads(res.stdout)

        # Check expires_at matches NotAfter
        for entry in body['processed']:
            if entry['action'] != 'issued':
                continue
            cert_path = entry['cert_path']
            expires_at_str = entry['expires_at']

            # Extract NotAfter from certificate
            cert_text = _run(f'openssl x509 -in {cert_path} -noout -text').stdout
            for line in cert_text.split('\n'):
                if 'Not After' in line:
                    date_str = line.split(': ')[1]
                    cert_time = datetime.datetime.strptime(date_str, '%b %d %H:%M:%S %Y %Z')
                    cert_time_iso = cert_time.strftime('%Y-%m-%dT%H:%M:%S.000Z')
                    break

            # Both should be within 1 second
            expires_dt = datetime.datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
            cert_dt = datetime.datetime.fromisoformat(cert_time_iso.replace('Z', '+00:00'))
            diff = abs((expires_dt - cert_dt).total_seconds())
            assert diff < 1, f'expires_at mismatch: {diff}s difference'

def test_invalid_algorithm_error():
    """Verify invalid algorithm is rejected."""
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ledger = tmp_path / 'services.csv'
        pki = tmp_path / 'pki'

        invalid_rows = [
            {
                'service': 'test',
                'hostname': 'test.example',
                'sans': 'DNS:test.example',
                'key_algorithm': 'ed25519',  # Unsupported
                'rotate_before_days': '30',
            }
        ]
        _write_ledger(ledger, invalid_rows)

        res = _run_worker(ledger, pki)
        assert res.returncode != 0
        body = json.loads(res.stdout)
        assert body['code'] == 'invalid_key_algorithm'

def test_idempotency():
    """Verify multiple runs produce consistent results."""
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ledger = tmp_path / 'services.csv'
        pki = tmp_path / 'pki'

        _write_ledger(ledger, _sample_rows())

        # Age intermediates
        old_time = int(time.time()) - (8 * 24 * 60 * 60)
        _run_worker(ledger, pki)
        for svc_name in ['worker', 'api']:
            created_at_file = pki / 'services' / svc_name / 'int_created_at'
            created_at_file.write_text(str(old_time))

        # First real run (with aged intermediates)
        res1 = _run_worker(ledger, pki)
        assert res1.returncode == 0
        body1 = json.loads(res1.stdout)

        # Second run should return action="reused"
        res2 = _run_worker(ledger, pki)
        assert res2.returncode == 0
        body2 = json.loads(res2.stdout)

        # Both should be consistent
        assert len(body1['processed']) == len(body2['processed'])
        for i, entry in enumerate(body1['processed']):
            assert entry['service'] == body2['processed'][i]['service']
            if entry['action'] == 'issued':
                assert body2['processed'][i]['action'] == 'reused'
                # Certs should be identical
                assert entry['expires_at'] == body2['processed'][i]['expires_at']

def test_audit_log_created_and_signed():
    """Verify audit log is created with HMAC-SHA256 signatures."""
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ledger = tmp_path / 'services.csv'
        pki = tmp_path / 'pki'

        _write_ledger(ledger, _sample_rows())

        # Age intermediates
        old_time = int(time.time()) - (8 * 24 * 60 * 60)
        _run_worker(ledger, pki)
        for svc_name in ['worker', 'api']:
            created_at_file = pki / 'services' / svc_name / 'int_created_at'
            created_at_file.write_text(str(old_time))

        # Issue certs (creates audit entries)
        res = _run_worker(ledger, pki)
        assert res.returncode == 0

        # Verify audit log exists
        audit_log = pki / 'audit.log'
        assert audit_log.exists(), 'Audit log not created'

        # Verify audit entries have valid HMAC signatures
        lines = audit_log.read_text().strip().split('\n')
        assert len(lines) > 0, 'Audit log is empty'

        expected_prev_hash = ''
        for line in lines:
            entry = json.loads(line)
            assert 'audit_signature' in entry, 'Missing audit_signature'
            assert 'audit_day' in entry, 'Missing audit_day'
            assert 'prev_hash' in entry, 'Missing prev_hash'
            assert 'entry_hash' in entry, 'Missing entry_hash'
            assert 'service' in entry
            assert 'action' in entry
            assert 'timestamp' in entry

            assert entry['prev_hash'] == expected_prev_hash, 'Audit prev_hash chain broken'
            expected_entry_hash = _entry_hash_from_payload(entry)
            assert entry['entry_hash'] == expected_entry_hash, 'Audit entry_hash mismatch'
            expected_prev_hash = entry['entry_hash']
            
            # Verify the HMAC signature is correct
            daily_key = _derive_daily_audit_key(AUDIT_SEED, entry['audit_day'])
            assert _verify_hmac_signature(entry, daily_key), f"Invalid signature for {entry['service']}/{entry['action']}"

def test_audit_tampering_detected():
    """Verify that tampering with audit log is detected."""
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ledger = tmp_path / 'services.csv'
        pki = tmp_path / 'pki'

        _write_ledger(ledger, _sample_rows())

        # Age intermediates and issue
        old_time = int(time.time()) - (8 * 24 * 60 * 60)
        _run_worker(ledger, pki)
        for svc_name in ['worker', 'api']:
            created_at_file = pki / 'services' / svc_name / 'int_created_at'
            created_at_file.write_text(str(old_time))

        res = _run_worker(ledger, pki)
        assert res.returncode == 0

        # Tamper with audit log (modify service name in first entry)
        audit_log = pki / 'audit.log'
        lines = audit_log.read_text().strip().split('\n')
        tampered = json.loads(lines[0])
        tampered['service'] = 'tampered-service'
        lines[0] = json.dumps(tampered)
        audit_log.write_text('\n'.join(lines) + '\n')

        # Re-run should detect tampering
        res = _run_worker(ledger, pki)
        assert res.returncode != 0, 'Should detect audit tampering'
        body = json.loads(res.stdout)
        assert body['code'] == 'invalid_signature', f"Expected invalid_signature, got {body['code']}"

def test_audit_reorder_detected():
    """Verify that reordering audit lines is detected via hash-chain validation."""
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ledger = tmp_path / 'services.csv'
        pki = tmp_path / 'pki'

        _write_ledger(ledger, _sample_rows())

        old_time = int(time.time()) - (8 * 24 * 60 * 60)
        _run_worker(ledger, pki)
        for svc_name in ['worker', 'api']:
            (pki / 'services' / svc_name / 'int_created_at').write_text(str(old_time))

        # Two runs produce multiple audit entries to make reordering meaningful.
        res = _run_worker(ledger, pki)
        assert res.returncode == 0
        res = _run_worker(ledger, pki)
        assert res.returncode == 0

        audit_log = pki / 'audit.log'
        lines = audit_log.read_text().strip().split('\n')
        assert len(lines) >= 2, 'Expected at least two audit entries for reorder test'

        # Swap first two lines and verify worker rejects.
        lines[0], lines[1] = lines[1], lines[0]
        audit_log.write_text('\n'.join(lines) + '\n')

        res = _run_worker(ledger, pki)
        assert res.returncode != 0, 'Expected worker to fail after audit line reorder'
        body = json.loads(res.stdout)
        assert body['code'] == 'invalid_signature', f"Expected invalid_signature, got {body['code']}"

def test_serial_number_sequencing():
    """Verify serial numbers increment monotonically across rotations."""
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ledger = tmp_path / 'services.csv'
        pki = tmp_path / 'pki'

        _write_ledger(ledger, _sample_rows())

        # Age and issue
        old_time = int(time.time()) - (8 * 24 * 60 * 60)
        _run_worker(ledger, pki)
        for svc_name in ['worker', 'api']:
            created_at_file = pki / 'services' / svc_name / 'int_created_at'
            created_at_file.write_text(str(old_time))

        res = _run_worker(ledger, pki)
        assert res.returncode == 0
        body = json.loads(res.stdout)

        # Extract serials from issued certs
        serials = {}
        for entry in body['processed']:
            if entry['action'] == 'issued':
                cert_path = entry['cert_path']
                serial = _cert_serial(cert_path)
                serials[entry['service']] = int(serial, 16)

        # Verify serials are >= 1
        for svc, serial in serials.items():
            assert serial >= 1, f'Serial for {svc} should be >= 1, got {serial}'

        # Trigger rotation by setting rotate_before_days > 90 (remaining validity)
        rotated_rows = _sample_rows()
        for r in rotated_rows:
            r['rotate_before_days'] = '91'
        _write_ledger(ledger, rotated_rows)

        res2 = _run_worker(ledger, pki)
        assert res2.returncode == 0
        body2 = json.loads(res2.stdout)

        # Verify new serials are higher
        for entry in body2['processed']:
            if entry['action'] == 'rotated':
                new_serial = int(_cert_serial(entry['cert_path']), 16)
                old_serial = serials[entry['service']]
                assert new_serial > old_serial, f"Serial not incremented for {entry['service']}: {old_serial} -> {new_serial}"

def test_serial_file_matches_certificate_serial():
    """Verify .serial content is lowercase hex and equals cert serial."""
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ledger = tmp_path / 'services.csv'
        pki = tmp_path / 'pki'

        _write_ledger(ledger, _sample_rows())

        old_time = int(time.time()) - (8 * 24 * 60 * 60)
        _run_worker(ledger, pki)
        for svc_name in ['worker', 'api']:
            (pki / 'services' / svc_name / 'int_created_at').write_text(str(old_time))

        res = _run_worker(ledger, pki)
        assert res.returncode == 0

        for svc in ['worker', 'api']:
            serial_file = pki / 'services' / svc / '.serial'
            cert_file = pki / 'services' / svc / 'cert.pem'
            stored_serial = serial_file.read_text().strip()
            cert_serial = _cert_serial(cert_file).lower()

            assert stored_serial == stored_serial.lower(), f'{svc} .serial must be lowercase hex'
            stored_num = int(stored_serial, 16)  # raises if non-hex
            cert_num = int(cert_serial, 16)
            assert stored_num == cert_num, (
                f'{svc} .serial mismatch: file={stored_serial}, cert={cert_serial} (numeric compare)'
            )

def test_output_sorted_by_service():
    """Verify processed array is sorted by service name."""
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ledger = tmp_path / 'services.csv'
        pki = tmp_path / 'pki'

        _write_ledger(ledger, _sample_rows())

        old_time = int(time.time()) - (8 * 24 * 60 * 60)
        _run_worker(ledger, pki)
        for svc_name in ['worker', 'api']:
            created_at_file = pki / 'services' / svc_name / 'int_created_at'
            created_at_file.write_text(str(old_time))

        res = _run_worker(ledger, pki)
        assert res.returncode == 0
        body = json.loads(res.stdout)

        # Extract service names in order
        services = [e['service'] for e in body['processed']]
        assert services == sorted(services), f'Output not sorted by service: {services} != {sorted(services)}'

def test_file_permissions():
    """Verify file permissions match specification."""
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ledger = tmp_path / 'services.csv'
        pki = tmp_path / 'pki'

        _write_ledger(ledger, _sample_rows())

        old_time = int(time.time()) - (8 * 24 * 60 * 60)
        _run_worker(ledger, pki)
        for svc_name in ['worker', 'api']:
            created_at_file = pki / 'services' / svc_name / 'int_created_at'
            created_at_file.write_text(str(old_time))

        res = _run_worker(ledger, pki)
        assert res.returncode == 0

        # Verify root key is 0600
        assert _mode(pki / 'ca' / 'ca.key.pem') == '600', 'Root key should be 0600'
        assert _mode(pki / 'ca' / 'ca.crt.pem') == '644', 'Root cert should be 0644'

        # Verify service keys/certs/metadata
        for svc in ['worker', 'api']:
            assert _mode(pki / 'services' / svc / 'key.pem') == '600', f'{svc} key should be 0600'
            assert _mode(pki / 'services' / svc / 'cert.pem') == '644', f'{svc} cert should be 0644'
            assert _mode(pki / 'services' / svc / '.serial') == '644', f'{svc} serial should be 0644'
            assert _mode(pki / 'services' / svc / 'int.key.pem') == '600', f'{svc} int key should be 0600'
            assert _mode(pki / 'services' / svc / 'int.crt.pem') == '644', f'{svc} int cert should be 0644'
            assert _mode(pki / 'services' / svc / 'int_created_at') == '644', f'{svc} int_created_at should be 0644'

        # Verify audit log
        audit_log = pki / 'audit.log'
        assert audit_log.exists(), 'Audit log should exist'
        assert _mode(audit_log) == '644', 'Audit log should be 0644'

        # Verify manifest.json permissions
        for svc in ['worker', 'api']:
            manifest = pki / 'services' / svc / 'manifest.json'
            assert manifest.exists(), f'manifest.json should exist for {svc}'
            assert _mode(manifest) == '644', f'{svc} manifest.json should be 0644'

        # Trigger rotation to also check crl.pem permissions
        rotated_rows = _sample_rows()
        for r in rotated_rows:
            r['rotate_before_days'] = '91'
        _write_ledger(ledger, rotated_rows)
        res2 = _run_worker(ledger, pki)
        assert res2.returncode == 0

        for svc in ['worker', 'api']:
            crl_file = pki / 'services' / svc / 'crl.pem'
            assert crl_file.exists(), f'crl.pem should exist for {svc} after rotation'
            assert _mode(crl_file) == '644', f'{svc} crl.pem should be 0644'

def test_rotation_action():
    """Verify rotation triggers action='rotated' with new expiry."""
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ledger = tmp_path / 'services.csv'
        pki = tmp_path / 'pki'

        _write_ledger(ledger, _sample_rows())

        # Age and issue
        old_time = int(time.time()) - (8 * 24 * 60 * 60)
        _run_worker(ledger, pki)
        for svc_name in ['worker', 'api']:
            created_at_file = pki / 'services' / svc_name / 'int_created_at'
            created_at_file.write_text(str(old_time))

        res1 = _run_worker(ledger, pki)
        assert res1.returncode == 0
        body1 = json.loads(res1.stdout)

        # Save original expiry dates
        original_expiry = {}
        for entry in body1['processed']:
            if entry['action'] == 'issued':
                original_expiry[entry['service']] = entry['expires_at']

        # Trigger rotation by setting rotate_before_days > 90
        rotated_rows = _sample_rows()
        for r in rotated_rows:
            r['rotate_before_days'] = '91'
        _write_ledger(ledger, rotated_rows)

        res2 = _run_worker(ledger, pki)
        assert res2.returncode == 0
        body2 = json.loads(res2.stdout)

        # Verify rotation occurred with new expiry
        for entry in body2['processed']:
            assert entry['action'] == 'rotated', f'{entry["service"]} should have action=rotated'
            cert_path = entry['cert_path']
            validity_seconds = _cert_validity_seconds(cert_path)
            assert validity_seconds is not None, f'Could not read validity for {entry["service"]} cert'
            expected = 90 * 24 * 3600
            assert abs(validity_seconds - expected) <= 60, (
                f'Validity must be exactly 90 days (within 60s), got {validity_seconds} seconds'
            )


def test_rotated_key_reuse_rejected():
    """Verify intermediate key reuse on rotation is rejected with rotated_key_reuse."""
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ledger = tmp_path / 'services.csv'
        pki = tmp_path / 'pki'

        rows = [_sample_rows()[0]]  # worker/rsa only
        _write_ledger(ledger, rows)

        # First run creates initial intermediate and key history.
        res = _run_worker(ledger, pki)
        assert res.returncode == 0, f'Worker failed: {res.stderr}'

        svc_dir = pki / 'services' / 'worker'
        int_key_path = svc_dir / 'int.key.pem'
        int_cert_path = svc_dir / 'int.crt.pem'
        key_history_path = svc_dir / '.int_key_hashes'

        assert int_key_path.exists(), 'Expected initial intermediate key'
        assert int_cert_path.exists(), 'Expected initial intermediate cert'
        assert key_history_path.exists(), 'Expected key history file'

        original_key = int_key_path.read_text()
        original_hash = _int_key_hash(int_key_path)

        history = [ln.strip() for ln in key_history_path.read_text().splitlines() if ln.strip()]
        assert original_hash in history, 'Initial key hash missing from history'

        # Force intermediate regeneration path.
        int_key_path.unlink()
        int_cert_path.unlink()

        # Wrap openssl so when worker generates new intermediate key, it reuses original key bytes.
        fakebin = tmp_path / 'fakebin'
        fakebin.mkdir()
        wrapper = fakebin / 'openssl'
        wrapper.write_text(
            '#!/usr/bin/env bash\n'
            'args=("$@")\n'
            'if [ "${args[0]}" = "genrsa" ] || [ "${args[0]}" = "genpkey" ]; then\n'
            '  for ((i = 1; i + 1 < ${#args[@]}; i += 1)); do\n'
            '    if [ "${args[i]}" = "-out" ] && [ "${args[i + 1]}" = "$TARGET_INT_KEY" ]; then\n'
            '      cp "$REUSE_KEY_PATH" "$TARGET_INT_KEY"\n'
            '      chmod 600 "$TARGET_INT_KEY"\n'
            '      exit 0\n'
            '    fi\n'
            '  done\n'
            'fi\n'
            'exec "$REAL_OPENSSL" "${args[@]}"\n'
        )
        wrapper.chmod(0o755)

        reuse_key_path = tmp_path / 'reuse_int.key.pem'
        reuse_key_path.write_text(original_key)
        reuse_key_path.chmod(0o600)

        real_openssl = _run('command -v openssl').stdout.strip()
        assert real_openssl, 'Unable to locate openssl for wrapper delegation'

        res = _run_worker(
            ledger,
            pki,
            extra_env={
                'PATH': f'{fakebin}:{os.environ.get("PATH", "")}',
                'REAL_OPENSSL': real_openssl,
                'REUSE_KEY_PATH': str(reuse_key_path),
                'TARGET_INT_KEY': str(int_key_path),
            },
        )

        assert res.returncode != 0, 'Expected non-zero exit for reused intermediate key rotation'
        body = json.loads(res.stdout)
        assert body.get('code') == 'rotated_key_reuse', (
            f"Expected rotated_key_reuse, got {body.get('code')}"
        )

if __name__ == '__main__':
    import sys
    pytest_args = sys.argv[1:]
    import pytest
    sys.exit(pytest.main([__file__] + pytest_args))


def test_crl_generated_on_rotation():
    """Verify that rotating a service certificate generates a CRL signed by the intermediate CA."""
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ledger = tmp_path / 'services.csv'
        pki = tmp_path / 'pki'

        _write_ledger(ledger, _sample_rows())

        # Age intermediates and issue certs
        old_time = int(time.time()) - (8 * 24 * 60 * 60)
        _run_worker(ledger, pki)
        for svc_name in ['worker', 'api']:
            (pki / 'services' / svc_name / 'int_created_at').write_text(str(old_time))
        res = _run_worker(ledger, pki)
        assert res.returncode == 0

        # Trigger rotation
        rotated_rows = _sample_rows()
        for r in rotated_rows:
            r['rotate_before_days'] = '91'
        _write_ledger(ledger, rotated_rows)
        res = _run_worker(ledger, pki)
        assert res.returncode == 0
        body = json.loads(res.stdout)
        for entry in body['processed']:
            assert entry['action'] == 'rotated', f'{entry["service"]} should have been rotated'

        # Verify CRL exists and is signed by the intermediate CA for each service
        for svc in ['worker', 'api']:
            crl_path = pki / 'services' / svc / 'crl.pem'
            int_cert_path = pki / 'services' / svc / 'int.crt.pem'
            assert crl_path.exists(), f'crl.pem missing for {svc}'

            verify = _run(f'openssl crl -in {crl_path} -CAfile {int_cert_path} -noout')
            assert verify.returncode == 0, (
                f'CRL for {svc} not signed by intermediate CA.\nstderr: {verify.stderr}'
            )


def test_crl_contains_revoked_serial():
    """Verify that the revoked certificate serial appears in the CRL after rotation."""
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ledger = tmp_path / 'services.csv'
        pki = tmp_path / 'pki'

        rows = [_sample_rows()[0]]  # Just 'worker' service
        _write_ledger(ledger, rows)

        # Age and issue initial cert
        old_time = int(time.time()) - (8 * 24 * 60 * 60)
        _run_worker(ledger, pki)
        (pki / 'services' / 'worker' / 'int_created_at').write_text(str(old_time))
        res = _run_worker(ledger, pki)
        assert res.returncode == 0

        # Record the original cert serial before rotation
        cert_path = pki / 'services' / 'worker' / 'cert.pem'
        serial_res = _run(f'openssl x509 -in {cert_path} -noout -serial')
        old_serial = serial_res.stdout.strip().replace('serial=', '').upper()

        # Trigger rotation
        rotated_rows = [dict(rows[0], rotate_before_days='91')]
        _write_ledger(ledger, rotated_rows)
        res = _run_worker(ledger, pki)
        assert res.returncode == 0
        assert json.loads(res.stdout)['processed'][0]['action'] == 'rotated'

        # Verify the old serial appears in the CRL
        crl_path = pki / 'services' / 'worker' / 'crl.pem'
        assert crl_path.exists(), 'crl.pem should exist after rotation'

        crl_text = _run(f'openssl crl -in {crl_path} -text -noout')
        assert old_serial in crl_text.stdout.upper(), (
            f'Revoked serial {old_serial} not found in CRL.\nCRL text:\n{crl_text.stdout}'
        )


def test_certificate_chain_validation():
    """Verify that service certificates are validated against the CA chain before issuance."""
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ledger = tmp_path / 'services.csv'
        pki = tmp_path / 'pki'

        _write_ledger(ledger, _sample_rows())

        # Age intermediates and issue certs
        old_time = int(time.time()) - (8 * 24 * 60 * 60)
        _run_worker(ledger, pki)
        for svc_name in ['worker', 'api']:
            (pki / 'services' / svc_name / 'int_created_at').write_text(str(old_time))
        
        res = _run_worker(ledger, pki)
        assert res.returncode == 0, f'Worker failed: {res.stderr}'
        body = json.loads(res.stdout)
        
        # Verify that each service certificate's chain is valid
        root_cert = pki / 'ca' / 'ca.crt.pem'
        for entry in body['processed']:
            if entry['action'] in ('issued', 'rotated'):
                cert_path = entry['cert_path']
                service_name = entry['service']
                int_cert = pki / 'services' / service_name / 'int.crt.pem'
                
                # Verify the service cert is signed by its intermediate CA
                # and the intermediate is signed by the root CA (full chain validation)
                verify_res = _run(
                    f'openssl verify -CAfile {root_cert} -untrusted {int_cert} {cert_path}'
                )
                assert verify_res.returncode == 0, (
                    f'Chain validation failed for {service_name}.\n'
                    f'stdout: {verify_res.stdout}\nstderr: {verify_res.stderr}'
                )
                
                # Additional check: verify intermediate is signed by root
                int_verify_res = _run(f'openssl verify -CAfile {root_cert} {int_cert}')
                assert int_verify_res.returncode == 0, (
                    f'Intermediate CA verification failed for {service_name}.\n'
                    f'stderr: {int_verify_res.stderr}'
                )


def test_manifest_created_and_valid():
    """Verify manifest.json is created with correct schema after cert issuance."""
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ledger = tmp_path / 'services.csv'
        pki = tmp_path / 'pki'

        _write_ledger(ledger, [_sample_rows()[0]])  # just 'worker'

        # Age intermediate and issue cert
        old_time = int(time.time()) - (8 * 24 * 60 * 60)
        _run_worker(ledger, pki)
        (pki / 'services' / 'worker' / 'int_created_at').write_text(str(old_time))

        res = _run_worker(ledger, pki)
        assert res.returncode == 0, f'Worker failed: {res.stderr}'

        manifest_path = pki / 'services' / 'worker' / 'manifest.json'
        assert manifest_path.exists(), 'manifest.json not created'

        manifest = json.loads(manifest_path.read_text())
        assert manifest.get('service') == 'worker', 'manifest.service incorrect'
        assert 'issued_certificates' in manifest, 'issued_certificates key missing'
        assert len(manifest['issued_certificates']) >= 1, 'No entries in manifest'

        entry = manifest['issued_certificates'][0]
        for field in ('serial', 'issued_at', 'expires_at', 'action', 'public_key_sha256', 'prev_entry_hash', 'entry_hash', 'entry_sig'):
            assert field in entry, f'manifest entry missing field: {field}'

        assert entry['action'] in ('issued', 'rotated', 'reused'), f"Unexpected action: {entry['action']}"
        # Verify issued_at is valid ISO-8601
        datetime.datetime.fromisoformat(entry['issued_at'].replace('Z', '+00:00'))

        _verify_manifest_chain(pki / 'services' / 'worker', 'worker')


def test_public_key_sha256_in_output():
    """Verify public_key_sha256 is present in JSON output and matches certificate public key."""
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ledger = tmp_path / 'services.csv'
        pki = tmp_path / 'pki'

        _write_ledger(ledger, [_sample_rows()[0]])  # just 'worker'

        # Age intermediate and issue cert
        old_time = int(time.time()) - (8 * 24 * 60 * 60)
        _run_worker(ledger, pki)
        (pki / 'services' / 'worker' / 'int_created_at').write_text(str(old_time))

        res = _run_worker(ledger, pki)
        assert res.returncode == 0, f'Worker failed: {res.stderr}'

        body = json.loads(res.stdout)
        issued = [e for e in body['processed'] if e['action'] in ('issued', 'rotated', 'reused')]
        assert issued, 'No issued/rotated/reused entries in output'

        entry = issued[0]
        assert 'public_key_sha256' in entry, 'public_key_sha256 missing from output entry'

        # Verify hash matches actual cert public key (oracle: sha256 of PEM pubkey string)
        cert_path = entry['cert_path']
        pubkey_res = _run(f'openssl x509 -in {cert_path} -pubkey -noout')
        assert pubkey_res.returncode == 0, 'Failed to extract public key from cert'
        expected_hash = hashlib.sha256(pubkey_res.stdout.encode()).hexdigest()
        assert entry['public_key_sha256'] == expected_hash, (
            f"public_key_sha256 mismatch: got {entry['public_key_sha256']}, expected {expected_hash}"
        )


def test_chain_validation_failure():
    """Verify that chain validation failure is detected and reported correctly."""
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ledger = tmp_path / 'services.csv'
        pki = tmp_path / 'pki'

        # Create ledger with worker service that needs rotation soon
        rows = [
            {
                'service': 'worker',
                'hostname': 'worker.internal.example',
                'sans': 'DNS:worker.internal.example',
                'key_algorithm': 'rsa',
                'rotate_before_days': '91',  # Rotate if less than 91 days remain (cert has ~90 days)
            },
        ]
        _write_ledger(ledger, rows)

        # Stage intermediates
        res = _run_worker(ledger, pki)
        assert res.returncode == 0, f'Worker failed: {res.stderr}'

        # Age intermediate to enable cert issuance
        old_time = int(time.time()) - (8 * 24 * 60 * 60)
        (pki / 'services' / 'worker' / 'int_created_at').write_text(str(old_time))
        
        # Issue initial certificate
        res = _run_worker(ledger, pki)
        assert res.returncode == 0, f'Worker failed: {res.stderr}'
        body = json.loads(res.stdout)
        assert any(e['action'] == 'issued' for e in body['processed']), 'Expected cert issuance'

        # Now corrupt the intermediate CA by replacing it with a self-signed cert
        # that is NOT signed by the root CA
        int_dir = pki / 'services' / 'worker'
        int_key = int_dir / 'int.key.pem'
        int_cert = int_dir / 'int.crt.pem'
        
        # Generate a new self-signed cert not signed by root
        _run(
            f'openssl req -x509 -newkey rsa:2048 -nodes '
            f'-keyout {int_key} -out {int_cert} -days 90 '
            f'-subj "/CN=corrupt-intermediate"'
        )

        # Try to run worker again - will attempt to rotate due to high rotate_before_days
        # This will fail with chain_validation_failed because intermediate is now corrupted
        res = _run_worker(ledger, pki)
        
        # Should fail with chain_validation_failed
        assert res.returncode != 0, 'Expected worker to fail with corrupted intermediate'
        body = json.loads(res.stdout)
        assert body.get('status') == 'error', f'Expected error status, got {body}'
        assert body.get('code') == 'chain_validation_failed', (
            f'Expected chain_validation_failed, got {body.get("code")}'
        )


def test_manifest_mismatch_on_corrupted_hash():
    """Verify manifest_mismatch error when manifest public key hash does not match certificate."""
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ledger = tmp_path / 'services.csv'
        pki = tmp_path / 'pki'

        _write_ledger(ledger, _sample_rows())

        # Age intermediate to enable cert issuance
        old_time = int(time.time()) - (8 * 24 * 60 * 60)
        _run_worker(ledger, pki)
        for svc_name in ['worker', 'api']:
            created_at_file = pki / 'services' / svc_name / 'int_created_at'
            created_at_file.write_text(str(old_time))

        # Issue initial certificates
        res = _run_worker(ledger, pki)
        assert res.returncode == 0, f'Worker failed: {res.stderr}'
        body = json.loads(res.stdout)
        assert any(e['action'] == 'issued' for e in body['processed']), 'Expected cert issuance'

        # Now corrupt the manifest for 'worker' service by modifying the public_key_sha256 hash
        manifest_path = pki / 'services' / 'worker' / 'manifest.json'
        with open(manifest_path) as f:
            manifest = json.load(f)
        
        # Corrupt the first entry's public_key_sha256 with garbage data
        if manifest['issued_certificates']:
            manifest['issued_certificates'][0]['public_key_sha256'] = 'deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef'
        
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f)

        # Run worker again - should fail with manifest_mismatch
        res = _run_worker(ledger, pki)
        assert res.returncode != 0, 'Expected worker to fail with corrupted manifest'
        body = json.loads(res.stdout)
        assert body.get('status') == 'error', f'Expected error status, got {body}'
        assert body.get('code') == 'manifest_mismatch', (
            f'Expected manifest_mismatch, got {body.get("code")}'
        )

def test_manifest_mismatch_on_key_reuse():
    """Verify manifest_mismatch error when rotated certificate reuses public key."""
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ledger = tmp_path / 'services.csv'
        pki = tmp_path / 'pki'

        _write_ledger(ledger, _sample_rows())

        # Age intermediate to enable cert issuance
        old_time = int(time.time()) - (8 * 24 * 60 * 60)
        _run_worker(ledger, pki)
        for svc_name in ['worker', 'api']:
            created_at_file = pki / 'services' / svc_name / 'int_created_at'
            created_at_file.write_text(str(old_time))

        # Issue initial certificates
        res = _run_worker(ledger, pki)
        assert res.returncode == 0, f'Worker failed: {res.stderr}'

        # Manually corrupt the manifest to simulate key reuse attack
        worker_dir = pki / 'services' / 'worker'
        old_key = worker_dir / 'key.pem'
        
        # Save the first key for potential later use
        first_key_content = old_key.read_text()

        # Force rotation by setting high rotate_before_days
        rotated_rows = _sample_rows()
        rotated_rows[0]['rotate_before_days'] = '91'  # Force rotation
        _write_ledger(ledger, rotated_rows)

        # Run worker to rotate (get a new cert with new key)
        res = _run_worker(ledger, pki)
        assert res.returncode == 0, f'Rotation failed: {res.stderr}'

        # Now restore the OLD key (simulating key reuse)
        old_key.write_text(first_key_content)

        # Run worker again - cert exists but key is old, which is a constraint violation
        # Actually, more precisely: if we manually restore the old public key to the cert file
        # or modify the manifest to claim a rotated cert has the same public key as a prior one,
        # that should trigger manifest_mismatch
        
        # Simpler approach: corrupt manifest to claim "rotated" entry has same pubkey as "issued" entry
        manifest_path = worker_dir / 'manifest.json'
        with open(manifest_path) as f:
            manifest = json.load(f)
        
        assert len(manifest['issued_certificates']) >= 2, (
            'Manifest should have >= 2 entries after forced rotation'
        )

        # Make the second (rotated) entry have the same public key as the first (issued)
        first_pubkey = manifest['issued_certificates'][0]['public_key_sha256']
        manifest['issued_certificates'][1]['public_key_sha256'] = first_pubkey

        with open(manifest_path, 'w') as f:
            json.dump(manifest, f)

        # Run worker again - should fail with manifest_mismatch
        res = _run_worker(ledger, pki)
        assert res.returncode != 0, 'Expected worker to fail with key reuse in manifest'
        body = json.loads(res.stdout)
        assert body.get('status') == 'error', f'Expected error status, got {body}'
        assert body.get('code') == 'manifest_mismatch', (
            f'Expected manifest_mismatch, got {body.get("code")}'
        )


def test_manifest_reorder_detected():
    """Verify reordering manifest entries is detected by prev_entry_hash/entry_sig checks."""
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ledger = tmp_path / 'services.csv'
        pki = tmp_path / 'pki'

        _write_ledger(ledger, [_sample_rows()[0]])

        old_time = int(time.time()) - (8 * 24 * 60 * 60)
        _run_worker(ledger, pki)
        (pki / 'services' / 'worker' / 'int_created_at').write_text(str(old_time))

        # Create at least two manifest entries.
        res = _run_worker(ledger, pki)
        assert res.returncode == 0
        rows = [_sample_rows()[0]]
        rows[0]['rotate_before_days'] = '91'
        _write_ledger(ledger, rows)
        res = _run_worker(ledger, pki)
        assert res.returncode == 0

        manifest_path = pki / 'services' / 'worker' / 'manifest.json'
        manifest = json.loads(manifest_path.read_text())
        assert len(manifest['issued_certificates']) >= 2

        entries = manifest['issued_certificates']
        entries[0], entries[1] = entries[1], entries[0]
        manifest['issued_certificates'] = entries
        manifest_path.write_text(json.dumps(manifest))

        res = _run_worker(ledger, pki)
        assert res.returncode != 0
        body = json.loads(res.stdout)
        assert body.get('code') == 'manifest_mismatch'


def test_randomized_manifest_integrity_reference():
    """Randomized multi-service sequence should satisfy manifest chain/signature invariants."""
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ledger = tmp_path / 'services.csv'
        pki = tmp_path / 'pki'

        rng = random.Random(secrets.randbelow(2**31))
        services = []
        for i in range(4):
            name = f'svc{i+1}'
            algo = 'rsa' if i % 2 == 0 else 'ec'
            services.append({
                'service': name,
                'hostname': f'{name}.example.internal',
                'sans': f'DNS:{name}.example.internal,DNS:{name}',
                'key_algorithm': algo,
                'rotate_before_days': '30',
            })

        _write_ledger(ledger, services)
        res = _run_worker(ledger, pki)
        assert res.returncode == 0

        old_time = int(time.time()) - (8 * 24 * 60 * 60)
        for svc in services:
            (pki / 'services' / svc['service'] / 'int_created_at').write_text(str(old_time))

        # Run several rounds with randomized rotate thresholds to generate mixed issued/reused/rotated history.
        for _ in range(5):
            for svc in services:
                svc['rotate_before_days'] = '91' if rng.random() < 0.45 else '5'
            _write_ledger(ledger, services)
            res = _run_worker(ledger, pki)
            assert res.returncode == 0, res.stderr

        for svc in services:
            svc_dir = pki / 'services' / svc['service']
            _verify_manifest_chain(svc_dir, svc['service'])


def test_intermediate_key_rotation_new_key_allowed():
    """Verify intermediate key rotation with new key is allowed."""
    with TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        ledger = tmpdir / 'ledger.csv'
        pki = tmpdir / 'pki'
        pki.mkdir()

        # Write initial ledger
        _write_ledger(ledger, _sample_rows())

        # Run worker to create intermediates and stage
        res = _run_worker(ledger, pki)
        assert res.returncode == 0, f'Worker failed: {res.stderr}'

        # Verify intermediates were created
        worker_dir = pki / 'services' / 'worker'
        int_cert_path = worker_dir / 'int.crt.pem'
        assert int_cert_path.exists(), 'Intermediate cert not created'

        # Verify key history file was created
        key_history_path = worker_dir / '.int_key_hashes'
        assert key_history_path.exists(), 'Key history file not created'
        
        # Read the initial key hash
        initial_key_hashes = key_history_path.read_text().strip().split('\n')
        assert len(initial_key_hashes) == 1, f'Expected 1 key hash, got {len(initial_key_hashes)}'
        
        # Now simulate expiry of the intermediate by manually deleting it
        # and setting a past creation time
        int_key_path = worker_dir / 'int.key.pem'
        int_key_path.unlink()
        int_cert_path.unlink()
        
        created_at_path = worker_dir / 'int_created_at'
        # Set creation time to 400 days ago (so intermediate "expired" after 365 days)
        old_timestamp = int(time.time()) - (400 * 24 * 60 * 60)
        created_at_path.write_text(str(old_timestamp))

        # Run worker again - should create a new intermediate with new key
        res = _run_worker(ledger, pki)
        assert res.returncode == 0, f'Worker should succeed with new intermediate key: {res.stderr}'

        # Verify new intermediate was created
        assert int_cert_path.exists(), 'New intermediate cert not created after rotation'
        
        # Verify key history now has 2 entries
        updated_key_hashes = key_history_path.read_text().strip().split('\n')
        assert len(updated_key_hashes) == 2, f'Expected 2 key hashes after rotation, got {len(updated_key_hashes)}'
        assert updated_key_hashes[0] != updated_key_hashes[1], 'New intermediate key should be different from old one'


def test_intermediate_key_history_persists():
    """Verify intermediate key history file tracks all keys across rotations."""
    with TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        ledger = tmpdir / 'ledger.csv'
        pki = tmpdir / 'pki'
        pki.mkdir()

        # Write initial ledger with two services (to verify per-service tracking)
        rows = [
            {
                'service': 'svc1',
                'hostname': 'svc1.example',
                'sans': 'DNS:svc1.example',
                'key_algorithm': 'rsa',
                'rotate_before_days': '30',
            },
            {
                'service': 'svc2',
                'hostname': 'svc2.example',
                'sans': 'DNS:svc2.example',
                'key_algorithm': 'ec',
                'rotate_before_days': '30',
            },
        ]
        _write_ledger(ledger, rows)

        # Run worker to create intermediates
        res = _run_worker(ledger, pki)
        assert res.returncode == 0, f'Worker failed: {res.stderr}'

        # Verify key history files were created for both services
        svc1_history = pki / 'services' / 'svc1' / '.int_key_hashes'
        svc2_history = pki / 'services' / 'svc2' / '.int_key_hashes'
        assert svc1_history.exists(), 'svc1 key history not created'
        assert svc2_history.exists(), 'svc2 key history not created'

        # Get initial key counts
        svc1_hashes_1 = svc1_history.read_text().strip().split('\n')
        svc2_hashes_1 = svc2_history.read_text().strip().split('\n')
        assert len(svc1_hashes_1) == 1, f'Expected 1 svc1 key, got {len(svc1_hashes_1)}'
        assert len(svc2_hashes_1) == 1, f'Expected 1 svc2 key, got {len(svc2_hashes_1)}'

        # Force rotation by deleting and aging intermediates
        for service in ['svc1', 'svc2']:
            svc_dir = pki / 'services' / service
            int_key = svc_dir / 'int.key.pem'
            int_cert = svc_dir / 'int.crt.pem'
            created_at = svc_dir / 'int_created_at'
            
            int_key.unlink()
            int_cert.unlink()
            old_timestamp = int(time.time()) - (400 * 24 * 60 * 60)
            created_at.write_text(str(old_timestamp))

        # Run worker again to create rotated intermediates
        res = _run_worker(ledger, pki)
        assert res.returncode == 0, f'Worker should succeed on rotation: {res.stderr}'

        # Verify key histories now have 2 entries each
        svc1_hashes_2 = svc1_history.read_text().strip().split('\n')
        svc2_hashes_2 = svc2_history.read_text().strip().split('\n')
        assert len(svc1_hashes_2) == 2, f'Expected 2 svc1 keys after rotation, got {len(svc1_hashes_2)}'
        assert len(svc2_hashes_2) == 2, f'Expected 2 svc2 keys after rotation, got {len(svc2_hashes_2)}'

        # Verify all keys are different (no accidental reuse)
        assert svc1_hashes_2[0] != svc1_hashes_2[1], 'svc1 rotated keys should be different'
        assert svc2_hashes_2[0] != svc2_hashes_2[1], 'svc2 rotated keys should be different'
        # Also verify services have independent key histories
        assert svc1_hashes_2[0] != svc2_hashes_2[0], 'Different services should have different keys'
