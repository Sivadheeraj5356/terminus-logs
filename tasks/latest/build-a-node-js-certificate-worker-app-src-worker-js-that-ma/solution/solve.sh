#!/usr/bin/env bash
set -euo pipefail

cd /app

cat > /app/src/worker.js <<'JS'
#!/usr/bin/env node

import fs from 'fs';
import os from 'os';
import path from 'path';
import { execFileSync } from 'child_process';
import crypto from 'crypto';

const STAGING_PERIOD_SECONDS = 7 * 24 * 60 * 60; // 7 days
const CERT_VALIDITY_DAYS = 90;
const INT_CERT_VALIDITY_DAYS = 365; // Intermediates valid for 1 year
const RSA_BITS = 2048;
const AUDIT_SEED = parseInt(process.env.AUDIT_SEED || '42', 10); // Deterministic seed for audit secret
const AUDIT_SECRET = crypto.createHash('sha256').update(`cert-audit-${AUDIT_SEED}`).digest();

function parseArgs(argv) {
	const out = {
		ledger: '/app/data/services.csv',
		pkiDir: '/app/pki',
	};
	for (let i = 2; i < argv.length; i += 1) {
		const arg = argv[i];
		if (arg === '--ledger') {
			out.ledger = argv[i + 1];
			i += 1;
		} else if (arg === '--pki-dir') {
			out.pkiDir = argv[i + 1];
			i += 1;
		}
	}
	return out;
}

function parseCsv(text) {
	const lines = text.trim().split(/\r?\n/);
	if (lines.length < 2) return [];
	const header = splitCsvLine(lines[0]);
	return lines.slice(1).filter(Boolean).map((line) => {
		const cols = splitCsvLine(line);
		const row = {};
		for (let i = 0; i < header.length; i += 1) row[header[i]] = cols[i] ?? '';
		return row;
	});
}

function splitCsvLine(line) {
	const out = [];
	let cur = '';
	let inQuote = false;
	for (let i = 0; i < line.length; i += 1) {
		const ch = line[i];
		if (ch === '"') {
			if (inQuote && line[i + 1] === '"') {
				cur += '"';
				i += 1;
			} else {
				inQuote = !inQuote;
			}
		} else if (ch === ',' && !inQuote) {
			out.push(cur);
			cur = '';
		} else {
			cur += ch;
		}
	}
	out.push(cur);
	return out;
}

function run(cmd, args) {
	try {
		return execFileSync(cmd, args, { encoding: 'utf-8' });
	} catch (e) {
		if (e.status) throw e;
		throw new Error(`${cmd} failed: ${e.message}`);
	}
}

function ensureRootCA(caDir) {
	const keyPath = path.join(caDir, 'ca.key.pem');
	const certPath = path.join(caDir, 'ca.crt.pem');

	if (!fs.existsSync(keyPath) || !fs.existsSync(certPath)) {
		run('openssl', ['genrsa', '-out', keyPath, String(RSA_BITS)]);
		run('openssl', [
			'req', '-new', '-x509', '-days', '3650', '-key', keyPath, '-out', certPath,
			'-subj', '/CN=openssl-ca-root'
		]);
		fs.chmodSync(keyPath, 0o600);
		fs.chmodSync(certPath, 0o644);
	}
}

function ensureServiceIntermediate(svcDir, svcName, caKeyPath, caCertPath, algo) {
	const intKeyPath = path.join(svcDir, 'int.key.pem');
	const intCertPath = path.join(svcDir, 'int.crt.pem');
	const createdAtPath = path.join(svcDir, 'int_created_at');
	const keyHistoryPath = path.join(svcDir, '.int_key_hashes');

	// Check if intermediate exists and is still valid
	let isExpired = false;
	if (fs.existsSync(intCertPath)) {
		const certText = run('openssl', ['x509', '-in', intCertPath, '-noout', '-text']);
		const notAfterMatch = certText.match(/Not After\s*:\s*(.+)/);
		if (notAfterMatch) {
			const expiresMs = new Date(notAfterMatch[1]).getTime();
			const nowMs = Date.now();
			isExpired = nowMs >= expiresMs;
		}
	}

	// If expired, rotate the intermediate
	if (isExpired && fs.existsSync(intKeyPath)) {
		// Intermediate has expired, need to rotate it
		fs.unlinkSync(intKeyPath);
		fs.unlinkSync(intCertPath);
	}

	if (!fs.existsSync(intKeyPath) || !fs.existsSync(intCertPath)) {
		// Generate intermediate key
		if (algo === 'ec') {
			run('openssl', ['ecparam', '-name', 'prime256v1', '-genkey', '-noout', '-out', intKeyPath]);
		} else {
			run('openssl', ['genrsa', '-out', intKeyPath, String(RSA_BITS)]);
		}

		// Validate key rotation: check if this key was ever used before
		if (fs.existsSync(keyHistoryPath)) {
			const newKeyHash = computeIntermediateKeyHash(intKeyPath);
			try {
				validateIntKeyRotation(keyHistoryPath, newKeyHash);
			} catch (e) {
				// Clean up the generated key file
				fs.unlinkSync(intKeyPath);
				throw e;
			}
		}

		// Create CSR for intermediate
		const csrPath = path.join(svcDir, 'int.csr.pem');
		run('openssl', [
			'req', '-new', '-key', intKeyPath, '-out', csrPath,
			'-subj', `/CN=${svcName}-int`
		]);

		// Sign intermediate with root CA (CA:TRUE extension)
		const extPath = path.join(svcDir, 'int.ext');
		fs.writeFileSync(extPath, 'basicConstraints=CA:TRUE\nkeyUsage=keyCertSign\n');
		run('openssl', [
			'x509', '-req', '-in', csrPath, '-CA', caCertPath, '-CAkey', caKeyPath,
			'-CAcreateserial', '-out', intCertPath, '-days', String(INT_CERT_VALIDITY_DAYS),
			'-extfile', extPath
		]);

		fs.unlinkSync(csrPath);
		fs.unlinkSync(extPath);
		fs.chmodSync(intKeyPath, 0o600);
		fs.chmodSync(intCertPath, 0o644);

		// Record key hash in history
		const keyHash = computeIntermediateKeyHash(intKeyPath);
		appendIntKeyHash(keyHistoryPath, keyHash);

		// Record creation time
		const now = Math.floor(Date.now() / 1000);
		fs.writeFileSync(createdAtPath, String(now));
		fs.chmodSync(createdAtPath, 0o644);
	}

	// Check if ready (older than staging period)
	const createdAt = parseInt(fs.readFileSync(createdAtPath, 'utf-8'));
	const now = Math.floor(Date.now() / 1000);
	const isReady = (now - createdAt) >= STAGING_PERIOD_SECONDS;

	return { isReady, createdAt, now };
}

function getExistingKeyAlgo(keyPath) {
	if (!fs.existsSync(keyPath)) return null;
	try {
		execFileSync('openssl', ['rsa', '-in', keyPath, '-check', '-noout'], { stdio: 'pipe' });
		return 'rsa';
	} catch {}
	try {
		execFileSync('openssl', ['ec', '-in', keyPath, '-check', '-noout'], { stdio: 'pipe' });
		return 'ec';
	} catch {}
	return null;
}

function getNextSerial(svcDir) {
	const serialPath = path.join(svcDir, '.serial');
	let current = 0;
	if (fs.existsSync(serialPath)) {
		current = parseInt(fs.readFileSync(serialPath, 'utf-8'), 16);
	}
	const next = current + 1;
	fs.writeFileSync(serialPath, next.toString(16).padStart(4, '0'));
	fs.chmodSync(serialPath, 0o644);
	return next.toString(16).padStart(4, '0');
}

function verifyCertificateChain(certPath, intCertPath, rootCertPath) {
	// Verify cert is signed by intermediate CA
	try {
		run('openssl', ['verify', '-CAfile', rootCertPath, '-untrusted', intCertPath, certPath]);
		return true;
	} catch (e) {
		throw new Error(`Certificate chain verification failed: ${e.message}`);
	}
}

function issueCertificate(svcDir, hostname, sans, algo, intKeyPath, intCertPath) {
	const keyPath = path.join(svcDir, 'key.pem');
	const csrPath = path.join(svcDir, 'csr.pem');
	const certPath = path.join(svcDir, 'cert.pem');
	const extPath = path.join(svcDir, 'cert.ext');

	// Generate service key
	if (algo === 'ec') {
		run('openssl', ['ecparam', '-name', 'prime256v1', '-genkey', '-noout', '-out', keyPath]);
	} else {
		run('openssl', ['genrsa', '-out', keyPath, String(RSA_BITS)]);
	}

	// Create CSR
	run('openssl', [
		'req', '-new', '-key', keyPath, '-out', csrPath,
		'-subj', `/CN=${hostname}`
	]);

	// Write SAN extension
	fs.writeFileSync(extPath, `subjectAltName=${sans}\n`);

	// Sign cert with intermediate
	const serial = getNextSerial(svcDir);
	run('openssl', [
		'x509', '-req', '-in', csrPath, '-CA', intCertPath, '-CAkey', intKeyPath,
		'-set_serial', '0x' + serial, '-out', certPath,
		'-days', String(CERT_VALIDITY_DAYS), '-extfile', extPath
	]);

	fs.unlinkSync(csrPath);
	fs.unlinkSync(extPath);
	fs.chmodSync(keyPath, 0o600);
	fs.chmodSync(certPath, 0o644);

	// Verify certificate chain (cert <- intermediate <- root)
	const rootCertPath = path.join(path.dirname(path.dirname(path.dirname(intCertPath))), 'ca', 'ca.crt.pem');
	verifyCertificateChain(certPath, intCertPath, rootCertPath);

	// Extract expires_at from certificate
	const certText = run('openssl', ['x509', '-in', certPath, '-noout', '-text']);
	const notAfterMatch = certText.match(/Not After\s*:\s*(.+)/);
	if (!notAfterMatch) throw new Error('Failed to extract NotAfter from certificate');

	const expiresAtMs = new Date(notAfterMatch[1]).getTime();
	const expiresAt = new Date(expiresAtMs).toISOString();

	return expiresAt;
}

function getRemainingDays(certPath) {
	const certText = run('openssl', ['x509', '-in', certPath, '-noout', '-text']);
	const notAfterMatch = certText.match(/Not After\s*:\s*(.+)/);
	if (!notAfterMatch) return -1;
	const expiresMs = new Date(notAfterMatch[1]).getTime();
	const nowMs = Date.now();
	return Math.ceil((expiresMs - nowMs) / (1000 * 60 * 60 * 24));
}

// ===== AUDIT TRAIL WITH HMAC-SHA256 =====

function initAuditLog(pkiDir) {
	const auditPath = path.join(pkiDir, 'audit.log');
	if (!fs.existsSync(auditPath)) {
		fs.writeFileSync(auditPath, '');
		fs.chmodSync(auditPath, 0o644);
	}
	return auditPath;
}

function getDailyAuditKey(dayEpoch) {
	// Derive daily key from AUDIT_SECRET (changes every day)
	return crypto.createHmac('sha256', AUDIT_SECRET).update(String(dayEpoch)).digest();
}

function canonicalAuditPayload(operation, prevHash) {
	return {
		action: operation.action,
		expires_at: operation.expires_at || '',
		key_algorithm: operation.key_algorithm || '',
		prev_hash: prevHash || '',
		service: operation.service,
		timestamp: operation.timestamp,
	};
}

function signOperation(operation, dayEpoch, prevHash) {
	const payload = canonicalAuditPayload(operation, prevHash);
	const canonical = JSON.stringify(payload, [
		'action',
		'expires_at',
		'key_algorithm',
		'prev_hash',
		'service',
		'timestamp',
	]);
	const entryHash = crypto.createHash('sha256').update(canonical).digest('hex');

	const dailyKey = getDailyAuditKey(dayEpoch);
	const signature = crypto.createHmac('sha256', dailyKey).update(canonical).digest('hex');

	return {
		...operation,
		prev_hash: prevHash || '',
		entry_hash: entryHash,
		audit_signature: signature,
		audit_day: dayEpoch,
	};
}

function verifyAuditLog(auditPath) {
	// Verify all existing signatures in audit log
	if (!fs.existsSync(auditPath)) return '';

	const lines = fs.readFileSync(auditPath, 'utf-8').trim().split('\n').filter(Boolean);
	let expectedPrevHash = '';
	for (const line of lines) {
		const entry = JSON.parse(line);
		const dayEpoch = entry.audit_day;
		const recordedSig = entry.audit_signature;

		const canonical = JSON.stringify(canonicalAuditPayload(entry, entry.prev_hash || ''), [
			'action',
			'expires_at',
			'key_algorithm',
			'prev_hash',
			'service',
			'timestamp',
		]);
		const expectedEntryHash = crypto.createHash('sha256').update(canonical).digest('hex');
		if ((entry.prev_hash || '') !== expectedPrevHash) {
			throw new Error(`invalid_signature: audit hash chain broken at ${entry.timestamp}`);
		}
		if ((entry.entry_hash || '') !== expectedEntryHash) {
			throw new Error(`invalid_signature: audit entry hash mismatch at ${entry.timestamp}`);
		}

		const dailyKey = getDailyAuditKey(dayEpoch);
		const expectedSig = crypto.createHmac('sha256', dailyKey).update(canonical).digest('hex');

		if (recordedSig !== expectedSig) {
			throw new Error(`invalid_signature: audit log tampered at ${entry.timestamp}`);
		}
		expectedPrevHash = expectedEntryHash;
	}
	return expectedPrevHash;
}

function appendAuditEntry(auditPath, signedOp) {
	const line = JSON.stringify(signedOp);
	fs.appendFileSync(auditPath, line + '\n');
}

// ===== CERTIFICATE REVOCATION LIST (CRL) =====

function toOpenSSLDateStr(d) {
	const yy = String(d.getUTCFullYear()).slice(-2);
	const mm = String(d.getUTCMonth() + 1).padStart(2, '0');
	const dd = String(d.getUTCDate()).padStart(2, '0');
	const hh = String(d.getUTCHours()).padStart(2, '0');
	const mi = String(d.getUTCMinutes()).padStart(2, '0');
	const ss = String(d.getUTCSeconds()).padStart(2, '0');
	return `${yy}${mm}${dd}${hh}${mi}${ss}Z`;
}

function initCrlDb(svcDir) {
	const crlDbDir = path.join(svcDir, 'crl_db');
	fs.mkdirSync(crlDbDir, { recursive: true });
	const indexPath = path.join(crlDbDir, 'index.txt');
	const crlNumPath = path.join(crlDbDir, 'crlnumber');
	if (!fs.existsSync(indexPath)) fs.writeFileSync(indexPath, '');
	if (!fs.existsSync(crlNumPath)) fs.writeFileSync(crlNumPath, '01\n');
	return crlDbDir;
}

function revokeAndUpdateCrl(svcDir, certToRevoke, intKeyPath, intCertPath) {
	const crlDbDir = initCrlDb(svcDir);
	const crlPath = path.join(svcDir, 'crl.pem');

	// Extract info from old cert for revocation index entry
	const serialRaw = run('openssl', ['x509', '-in', certToRevoke, '-noout', '-serial'])
		.trim().replace('serial=', '').toUpperCase().padStart(4, '0');
	const endDateRaw = run('openssl', ['x509', '-in', certToRevoke, '-noout', '-enddate'])
		.trim().replace('notAfter=', '');
	const notAfterFmt = toOpenSSLDateStr(new Date(endDateRaw));
	const subjectRaw = run('openssl', ['x509', '-in', certToRevoke, '-noout', '-subject', '-nameopt', 'compat'])
		.trim();
	const subjectLine = subjectRaw.replace(/^subject=\s*/, '');
	const revTimeFmt = toOpenSSLDateStr(new Date());

	// Append revoked entry: R<TAB>notAfter<TAB>revTime,reason<TAB>serial<TAB>unknown<TAB>subject
	const indexEntry = `R\t${notAfterFmt}\t${revTimeFmt},unspecified\t${serialRaw}\tunknown\t${subjectLine}\n`;
	fs.appendFileSync(path.join(crlDbDir, 'index.txt'), indexEntry);

	// Write temporary CA config for CRL generation
	const cnfPath = path.join(svcDir, '_crl_gen.cnf');
	const cnfContent = [
		'[ca]',
		'default_ca = CA_default',
		'[CA_default]',
		`database = ${path.join(crlDbDir, 'index.txt')}`,
		`crlnumber = ${path.join(crlDbDir, 'crlnumber')}`,
		'default_crl_days = 30',
		'default_md = sha256',
		'preserve = no',
		'policy = policy_anything',
		'[policy_anything]',
		'commonName = supplied',
	].join('\n') + '\n';
	fs.writeFileSync(cnfPath, cnfContent);

	// Generate CRL signed by intermediate CA
	run('openssl', [
		'ca', '-batch', '-config', cnfPath, '-gencrl',
		'-keyfile', intKeyPath, '-cert', intCertPath,
		'-out', crlPath,
	]);

	fs.chmodSync(crlPath, 0o644);
	try { fs.unlinkSync(cnfPath); } catch { /* ignore */ }
}

// ===== CERTIFICATE MANIFEST WITH PUBLIC KEY PINNING =====

function computePublicKeyHash(certPath) {
	const pubKeyPem = run('openssl', ['x509', '-in', certPath, '-pubkey', '-noout']);
	const hash = crypto.createHash('sha256').update(pubKeyPem).digest('hex');
	return hash;
}

function computeIntermediateKeyHash(intKeyPath) {
	// Extract public key from intermediate private key and compute hash
	const pubKeyPem = run('openssl', ['pkey', '-in', intKeyPath, '-pubout']);
	const hash = crypto.createHash('sha256').update(pubKeyPem).digest('hex');
	return hash;
}

function loadIntKeyHistory(keyHistoryPath) {
	if (!fs.existsSync(keyHistoryPath)) return [];
	const lines = fs.readFileSync(keyHistoryPath, 'utf-8').trim().split('\n').filter(Boolean);
	return lines;
}

function appendIntKeyHash(keyHistoryPath, hash) {
	fs.appendFileSync(keyHistoryPath, hash + '\n');
	fs.chmodSync(keyHistoryPath, 0o644);
}

function validateIntKeyRotation(keyHistoryPath, newKeyHash) {
	const history = loadIntKeyHistory(keyHistoryPath);
	if (history.includes(newKeyHash)) {
		throw new Error(`rotated_key_reuse: intermediate key rotation attempted to reuse a prior key`);
	}
}

function loadManifest(manifestPath) {
	if (fs.existsSync(manifestPath)) {
		return JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
	}
	return { service: '', issued_certificates: [] };
}

function saveManifest(manifestPath, manifest) {
	fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
	fs.chmodSync(manifestPath, 0o644);
}

function deriveManifestSecret(serviceName, keyHistoryPath) {
	const history = loadIntKeyHistory(keyHistoryPath);
	const anchor = history.length > 0 ? history[0] : 'bootstrap';
	return crypto.createHash('sha256').update(`manifest:${serviceName}:${anchor}`).digest();
}

function canonicalManifestEntry(entry) {
	return {
		action: entry.action,
		expires_at: entry.expires_at,
		issued_at: entry.issued_at,
		prev_entry_hash: entry.prev_entry_hash || '',
		public_key_sha256: entry.public_key_sha256,
		serial: entry.serial,
	};
}

function manifestCanonicalJson(entry) {
	return JSON.stringify(canonicalManifestEntry(entry), [
		'action',
		'expires_at',
		'issued_at',
		'prev_entry_hash',
		'public_key_sha256',
		'serial',
	]);
}

function validateManifestIntegrity(svcDir, serviceName, manifest, manifestSecret) {
	if (manifest.service && manifest.service !== serviceName) {
		throw new Error(`Manifest service mismatch for ${serviceName}`);
	}

	let expectedPrevHash = '';
	let prevIssuedAt = '';

	for (const entry of manifest.issued_certificates) {
		for (const k of ['serial', 'issued_at', 'expires_at', 'action', 'public_key_sha256', 'prev_entry_hash', 'entry_hash', 'entry_sig']) {
			if (!(k in entry)) {
				throw new Error(`Manifest missing field ${k} for ${serviceName}`);
			}
		}

		if (entry.issued_at < prevIssuedAt) {
			throw new Error(`Manifest issued_at ordering violation for ${serviceName}`);
		}
		prevIssuedAt = entry.issued_at;

		if ((entry.prev_entry_hash || '') !== expectedPrevHash) {
			throw new Error(`Manifest hash chain broken for ${serviceName}`);
		}

		const canonical = manifestCanonicalJson(entry);
		const expectedHash = crypto.createHash('sha256').update(canonical).digest('hex');
		const expectedSig = crypto.createHmac('sha256', manifestSecret).update(canonical).digest('hex');
		if (entry.entry_hash !== expectedHash || entry.entry_sig !== expectedSig) {
			throw new Error(`Manifest signature mismatch for ${serviceName}`);
		}

		expectedPrevHash = expectedHash;
	}

	if (manifest.issued_certificates.length > 0) {
		const latest = manifest.issued_certificates[manifest.issued_certificates.length - 1];
		const certPath = path.join(svcDir, 'cert.pem');
		if (fs.existsSync(certPath)) {
			const actualHash = computePublicKeyHash(certPath);
			if (actualHash !== latest.public_key_sha256) {
				throw new Error(`Manifest public_key_sha256 mismatch for ${serviceName} serial ${latest.serial}`);
			}
		}
	}

	const rotatedEntries = manifest.issued_certificates.filter(e => e.action === 'rotated');
	for (let i = 0; i < rotatedEntries.length; i++) {
		const rotatedEntry = rotatedEntries[i];
		const priorHashes = manifest.issued_certificates
			.slice(0, manifest.issued_certificates.indexOf(rotatedEntry))
			.filter(e => e.action === 'issued' || e.action === 'rotated')
			.map(e => e.public_key_sha256);
		if (priorHashes.includes(rotatedEntry.public_key_sha256)) {
			throw new Error(`Key reuse violation: rotated entry has same key hash as prior entry (${serviceName})`);
		}
	}
}

function updateManifestWithNewCert(manifest, service, serial, action, expiresAt, publicKeyHash, manifestSecret) {
	manifest.service = service;
	const now = new Date();
	const prevEntry = manifest.issued_certificates.length > 0
		? manifest.issued_certificates[manifest.issued_certificates.length - 1]
		: null;
	const entry = {
		serial,
		issued_at: now.toISOString(),
		expires_at: expiresAt,
		action,
		public_key_sha256: publicKeyHash,
		prev_entry_hash: prevEntry ? prevEntry.entry_hash : '',
	};
	const canonical = manifestCanonicalJson(entry);
	entry.entry_hash = crypto.createHash('sha256').update(canonical).digest('hex');
	entry.entry_sig = crypto.createHmac('sha256', manifestSecret).update(canonical).digest('hex');
	manifest.issued_certificates.push(entry);
}


async function main() {
	const args = parseArgs(process.argv);
	const ledger = parseCsv(fs.readFileSync(args.ledger, 'utf-8'));
	const caDir = path.join(args.pkiDir, 'ca');

	// Ensure pki directory exists before audit log init
	fs.mkdirSync(args.pkiDir, { recursive: true });

	const auditPath = initAuditLog(args.pkiDir);
	let auditChainTail = '';

	// Verify audit log integrity
	try {
		auditChainTail = verifyAuditLog(auditPath);
	} catch (e) {
		console.log(JSON.stringify({ status: 'error', code: 'invalid_signature', message: e.message }));
		process.exit(1);
	}

	// Ensure root CA
	fs.mkdirSync(caDir, { recursive: true });
	const caKeyPath = path.join(caDir, 'ca.key.pem');
	const caCertPath = path.join(caDir, 'ca.crt.pem');
	ensureRootCA(caDir);

	const processed = [];
	const errors = [];
	const now = Math.floor(Date.now() / 1000);
	const dayEpoch = Math.floor(Date.now() / (24 * 60 * 60 * 1000));

	for (const row of ledger) {
		const service = row['service'] || '';
		const hostname = row['hostname'] || '';
		const sans = row['sans'] || '';
		const algo = (row['key_algorithm'] || 'rsa').toLowerCase();
		const rotateBeforeDays = parseInt(row['rotate_before_days'] || '30', 10);
		const rotateBefore = rotateBeforeDays;

		if (!service || !hostname) continue;

		if (algo !== 'rsa' && algo !== 'ec') {
			errors.push({ code: 'invalid_key_algorithm', service });
			continue;
		}

		try {
			const svcDir = path.join(args.pkiDir, 'services', service);
		fs.mkdirSync(svcDir, { recursive: true });

		const keyHistoryPath = path.join(svcDir, '.int_key_hashes');

		// Load manifest (validation occurs after intermediate setup so secret derivation is stable)
		const manifestPath = path.join(svcDir, 'manifest.json');
		let manifest = loadManifest(manifestPath);
		if (!manifest.service) manifest.service = service;

		// Ensure/check intermediate
		const intRes = ensureServiceIntermediate(svcDir, service, caKeyPath, caCertPath, algo);

		let manifestSecret;
		try {
			manifestSecret = deriveManifestSecret(service, keyHistoryPath);
			validateManifestIntegrity(svcDir, service, manifest, manifestSecret);
		} catch (e) {
			errors.push({ code: 'manifest_mismatch', service });
			continue;
		}

		if (!intRes.isReady) {
			// Intermediate too new, return staged
			const nextSerial = getNextSerial(svcDir);
			processed.push({
				service,
				action: 'staged',
				staged_at: new Date().toISOString(),
				serial: nextSerial,
			});
			continue;
		}

		const intKeyPath = path.join(svcDir, 'int.key.pem');
		const intCertPath = path.join(svcDir, 'int.crt.pem');
		const keyPath = path.join(svcDir, 'key.pem');
		const certPath = path.join(svcDir, 'cert.pem');

		// Check if cert exists
		if (!fs.existsSync(certPath)) {
			// Check algorithm lock-in
			const existingAlgo = getExistingKeyAlgo(keyPath);
			if (existingAlgo && existingAlgo !== algo) {
				errors.push({ code: 'algorithm_mismatch', service });
				continue;
			}

			// Issue new certificate
			const expiresAt = issueCertificate(svcDir, hostname, sans, algo, intKeyPath, intCertPath);
			const issuedPubKeyHash = computePublicKeyHash(certPath);
			const issuedSerial = run('openssl', ['x509', '-in', certPath, '-noout', '-serial']).trim().replace('serial=', '').toLowerCase();
			updateManifestWithNewCert(manifest, service, issuedSerial, 'issued', expiresAt, issuedPubKeyHash, manifestSecret);
			saveManifest(manifestPath, manifest);
			const op = {
				service,
				action: 'issued',
				key_algorithm: algo,
				cert_path: certPath,
				key_path: keyPath,
				expires_at: expiresAt,
				timestamp: new Date().toISOString(),
			};
			const signed = signOperation(op, dayEpoch, auditChainTail);
			appendAuditEntry(auditPath, signed);
			auditChainTail = signed.entry_hash;
			processed.push({
				service,
				action: 'issued',
				key_algorithm: algo,
				cert_path: certPath,
				key_path: keyPath,
				expires_at: expiresAt,
				public_key_sha256: issuedPubKeyHash,
			});
		} else {
			// Cert exists: check algorithm lock-in
			const existingAlgo = getExistingKeyAlgo(keyPath);
			if (existingAlgo !== algo) {
				errors.push({ code: 'algorithm_mismatch', service });
				continue;
			}

			const remainingDays = getRemainingDays(certPath);

			if (remainingDays < rotateBefore) {
				// Save old cert before overwriting so we can revoke it
				const oldCertTmp = path.join(svcDir, '_prev_cert.pem');
				fs.copyFileSync(certPath, oldCertTmp);

				// Rotate
				const expiresAt = issueCertificate(svcDir, hostname, sans, algo, intKeyPath, intCertPath);

				// Revoke old cert and update CRL
				revokeAndUpdateCrl(svcDir, oldCertTmp, intKeyPath, intCertPath);
				try { fs.unlinkSync(oldCertTmp); } catch { /* ignore */ }
				const rotatedPubKeyHash = computePublicKeyHash(certPath);
				const rotatedSerial = run('openssl', ['x509', '-in', certPath, '-noout', '-serial']).trim().replace('serial=', '').toLowerCase();
				updateManifestWithNewCert(manifest, service, rotatedSerial, 'rotated', expiresAt, rotatedPubKeyHash, manifestSecret);
				saveManifest(manifestPath, manifest);
				const op = {
					service,
					action: 'rotated',
					key_algorithm: algo,
					cert_path: certPath,
					key_path: keyPath,
					expires_at: expiresAt,
					timestamp: new Date().toISOString(),
				};
				const signed = signOperation(op, dayEpoch, auditChainTail);
				appendAuditEntry(auditPath, signed);
				auditChainTail = signed.entry_hash;
				processed.push({
					service,
					action: 'rotated',
					key_algorithm: algo,
					cert_path: certPath,
					key_path: keyPath,
					expires_at: expiresAt,
					public_key_sha256: rotatedPubKeyHash,
				});
			} else {
				// Reuse existing cert
				const certText = run('openssl', ['x509', '-in', certPath, '-noout', '-text']);
				const notAfterMatch = certText.match(/Not After\s*:\s*(.+)/);
				const expiresAtMs = new Date(notAfterMatch[1]).getTime();
				const expiresAt = new Date(expiresAtMs).toISOString();
				const reusedPubKeyHash = computePublicKeyHash(certPath);
				const reusedSerial = run('openssl', ['x509', '-in', certPath, '-noout', '-serial']).trim().replace('serial=', '').toLowerCase();
				updateManifestWithNewCert(manifest, service, reusedSerial, 'reused', expiresAt, reusedPubKeyHash, manifestSecret);
				saveManifest(manifestPath, manifest);
				const op = {
					service,
					action: 'reused',
					key_algorithm: algo,
					cert_path: certPath,
					key_path: keyPath,
					expires_at: expiresAt,
					timestamp: new Date().toISOString(),
				};
				const signed = signOperation(op, dayEpoch, auditChainTail);
				appendAuditEntry(auditPath, signed);
				auditChainTail = signed.entry_hash;
				processed.push({
					service,
					action: 'reused',
					key_algorithm: algo,
					cert_path: certPath,
					key_path: keyPath,
					expires_at: expiresAt,
					public_key_sha256: reusedPubKeyHash,
				});
			}
		}
	} catch (e) {
		if (e.message && e.message.includes('Certificate chain verification failed')) {
			errors.push({ code: 'chain_validation_failed', service });
		} else if (e.message && e.message.includes('rotated_key_reuse')) {
			errors.push({ code: 'rotated_key_reuse', service });
		} else {
			throw e;
		}
	}
	}

	if (errors.length > 0) {
		console.log(JSON.stringify({ status: 'error', ...errors[0] }));
		process.exit(1);
	}

	// Sort processed array by service name
	processed.sort((a, b) => a.service.localeCompare(b.service));

	console.log(JSON.stringify({ status: 'ok', processed }));
}

main().catch((e) => {
	console.log(JSON.stringify({ status: 'error', code: 'internal_error', message: e.message }));
	process.exit(1);
});
JS

node /app/src/worker.js "$@"
