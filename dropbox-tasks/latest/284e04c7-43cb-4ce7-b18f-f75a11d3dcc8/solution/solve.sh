#!/bin/bash
set -euo pipefail

app_root="${APP_ROOT:-/app}"

cat > "${app_root}/src/worker.js" <<'EOF'
import {
  createDecipheriv,
  createHash,
  createHmac,
  createPublicKey,
  hkdfSync,
  timingSafeEqual,
  verify as verifySignature,
} from 'node:crypto';
import process from 'node:process';
import { DuckDBInstance } from '@duckdb/node-api';
import { canonicalJson } from './canonical-json.js';
import {
  FAILURE,
  KEY_ATTESTATION_THRESHOLD,
  LEASE_SECONDS,
  MAGIC,
  MAX_CIPHERTEXT_BYTES,
  IMAGE_ANNOTATION,
  IMAGE_MANIFEST_ANNOTATION,
} from './constants.js';
import { ContractError } from './errors.js';
import { rotationDecision } from './policy.js';
import { addSeconds, normalizeTimestamp } from './time.js';

const BASE64 = /^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/;
const BASE64URL = /^[A-Za-z0-9_-]+$/;
const SECRET_NAME = /^[A-Z][A-Z0-9_]{0,63}$/;
const WITNESS_ID = /^[a-z][a-z0-9-]{0,31}$/;
const PAYLOAD_KEYS = [
  'deploymentId',
  'expiresAt',
  'issuedAt',
  'notBefore',
  'rotationCounter',
  'secretName',
  'value',
];
const ZERO_HASH = '0'.repeat(64);

function contract(code, message) {
  throw new ContractError(code, message);
}

function canonicalBase64(text, expectedLength = undefined) {
  if (typeof text !== 'string' || text.length === 0 || text.length % 4 !== 0 || !BASE64.test(text)) {
    return null;
  }
  const decoded = Buffer.from(text, 'base64');
  if ((expectedLength !== undefined && decoded.length !== expectedLength)
      || decoded.toString('base64') !== text) return null;
  return decoded;
}

function parseEnvelopeLabel(labelsJson) {
  let labels;
  try {
    labels = JSON.parse(labelsJson);
  } catch {
    contract(FAILURE.ENVELOPE, 'invalid OCI labels JSON');
  }
  if (labels === null || Array.isArray(labels) || typeof labels !== 'object') {
    contract(FAILURE.ENVELOPE, 'OCI labels are not an object');
  }
  const partKeys = Object.keys(labels).filter((key) => key.startsWith(`${IMAGE_ANNOTATION}.part.`));
  const hasDirect = Object.hasOwn(labels, IMAGE_ANNOTATION);
  const hasManifest = Object.hasOwn(labels, IMAGE_MANIFEST_ANNOTATION);
  if (hasDirect === hasManifest) {
    contract(FAILURE.ENVELOPE, 'exactly one PFSEAL transport is required');
  }
  let encoded;
  if (hasDirect) {
    if (partKeys.length !== 0 || typeof labels[IMAGE_ANNOTATION] !== 'string') {
      contract(FAILURE.ENVELOPE, 'direct PFSEAL transport is invalid');
    }
    encoded = labels[IMAGE_ANNOTATION];
  } else {
    const manifestText = labels[IMAGE_MANIFEST_ANNOTATION];
    let manifest;
    try {
      manifest = JSON.parse(manifestText);
    } catch {
      contract(FAILURE.ENVELOPE, 'chunk manifest is invalid JSON');
    }
    if (typeof manifestText !== 'string' || manifest === null || Array.isArray(manifest)
        || typeof manifest !== 'object' || canonicalJson(manifest) !== manifestText
        || JSON.stringify(Object.keys(manifest).sort()) !== '["count","sha256"]'
        || !Number.isInteger(manifest.count) || manifest.count < 2 || manifest.count > 32
        || typeof manifest.sha256 !== 'string' || !/^[0-9a-f]{64}$/.test(manifest.sha256)) {
      contract(FAILURE.ENVELOPE, 'chunk manifest is invalid');
    }
    const expectedKeys = Array.from(
      { length: manifest.count },
      (_, index) => `${IMAGE_ANNOTATION}.part.${String(index).padStart(3, '0')}`,
    );
    if (partKeys.length !== expectedKeys.length
        || expectedKeys.some((key) => !Object.hasOwn(labels, key))) {
      contract(FAILURE.ENVELOPE, 'chunk set is invalid');
    }
    const chunks = expectedKeys.map((key) => labels[key]);
    if (chunks.some((chunk) => typeof chunk !== 'string' || chunk.length < 1
        || chunk.length > 1024 || !/^[\x00-\x7f]+$/.test(chunk))) {
      contract(FAILURE.ENVELOPE, 'chunk value is invalid');
    }
    encoded = chunks.join('');
    const transportHash = createHash('sha256').update(Buffer.from(encoded, 'utf8')).digest('hex');
    if (transportHash !== manifest.sha256) {
      contract(FAILURE.ENVELOPE, 'chunk transport hash is invalid');
    }
  }
  if (encoded.length === 0 || encoded.length % 4 !== 0 || !BASE64.test(encoded)) {
    contract(FAILURE.ENVELOPE, 'PFSEAL label is not canonical base64');
  }
  const bytes = Buffer.from(encoded, 'base64');
  if (bytes.toString('base64') !== encoded || bytes.length < 74) {
    contract(FAILURE.ENVELOPE, 'PFSEAL envelope length is invalid');
  }
  if (!bytes.subarray(0, 7).equals(MAGIC) || bytes[7] !== 0) {
    contract(FAILURE.ENVELOPE, 'PFSEAL prefix is invalid');
  }
  const keyVersion = bytes.readUInt16BE(8);
  const ciphertextLength = bytes.readUInt32BE(22);
  if (keyVersion === 0 || ciphertextLength < 1 || ciphertextLength > MAX_CIPHERTEXT_BYTES) {
    contract(FAILURE.ENVELOPE, 'PFSEAL numeric field is invalid');
  }
  if (bytes.length !== 74 + ciphertextLength) {
    contract(FAILURE.ENVELOPE, 'PFSEAL envelope has trailing or missing bytes');
  }
  return {
    keyVersion,
    nonce: bytes.subarray(10, 22),
    headerCore: bytes.subarray(0, 26),
    headerMac: bytes.subarray(26, 58),
    header: bytes.subarray(0, 58),
    ciphertext: bytes.subarray(58, 58 + ciphertextLength),
    tag: bytes.subarray(58 + ciphertextLength),
  };
}

async function readRows(connection, sql, values = undefined) {
  const reader = values === undefined
    ? await connection.runAndReadAll(sql)
    : await connection.runAndReadAll(sql, values);
  return reader.getRowObjectsJS();
}

function safeUnsigned(value, field) {
  const number = typeof value === 'bigint' ? Number(value) : value;
  if (!Number.isSafeInteger(number) || number < 0) {
    throw new Error(`${field} is outside the JavaScript safe integer range`);
  }
  return number;
}

async function begin(connection) {
  await connection.run('BEGIN TRANSACTION');
}

async function rollback(connection) {
  try {
    await connection.run('ROLLBACK');
  } catch {
    // Preserve the original database error.
  }
}

async function claimNext(connection, options) {
  await begin(connection);
  try {
    const rows = await readRows(connection, `
      SELECT j.job_id, j.deployment_id, j.image_digest, j.metadata_revision,
             i.image_annotations_json
      FROM prefect_secret_jobs AS j
      LEFT JOIN prefect_images AS i ON i.image_digest = j.image_digest
      WHERE j.status = 'pending'
         OR (j.status = 'processing' AND j.lease_until IS NOT NULL
             AND j.lease_until <= CAST($at AS TIMESTAMP))
      ORDER BY j.job_id
      LIMIT 1
    `, { at: options.at });
    if (rows.length === 0) {
      await connection.run('COMMIT');
      return null;
    }
    const row = rows[0];
    const jobId = safeUnsigned(row.job_id, 'job_id');
    const metadataRevision = safeUnsigned(row.metadata_revision, 'metadata_revision');
    const leaseUntil = addSeconds(options.at, LEASE_SECONDS);
    await connection.run(`
      UPDATE prefect_secret_jobs
         SET status = 'processing',
             attempt_count = attempt_count + 1,
             lease_owner = $worker_id,
             lease_until = CAST($lease_until AS TIMESTAMP),
             completed_at = NULL,
             failure_code = NULL
       WHERE job_id = $job_id
    `, {
      worker_id: options.workerId,
      lease_until: leaseUntil,
      job_id: BigInt(jobId),
    });
    await connection.run('COMMIT');
    return {
      jobId,
      deploymentId: row.deployment_id,
      imageDigest: row.image_digest,
      metadataRevision,
      labelsJson: row.image_annotations_json,
    };
  } catch (error) {
    await rollback(connection);
    throw error;
  }
}

function decodeShares(metadata, version) {
  const prefix = `pfseal.key.v${version}.`;
  const share0Text = metadata.get(`${prefix}share0`);
  const share1Text = metadata.get(`${prefix}share1`);
  const share2Text = metadata.get(`${prefix}share2`);
  if (typeof share0Text !== 'string' || !/^hex:[0-9a-f]{64}$/.test(share0Text)) {
    contract(FAILURE.METADATA, 'share0 is invalid');
  }
  if (typeof share1Text !== 'string' || !share1Text.startsWith('b64:')) {
    contract(FAILURE.METADATA, 'share1 is invalid');
  }
  const share1 = canonicalBase64(share1Text.slice(4), 32);
  if (!share1) contract(FAILURE.METADATA, 'share1 is invalid');
  if (typeof share2Text !== 'string' || !share2Text.startsWith('b64url:')) {
    contract(FAILURE.METADATA, 'share2 is invalid');
  }
  const share2Encoded = share2Text.slice(7);
  if (share2Encoded.length === 0 || !BASE64URL.test(share2Encoded)) {
    contract(FAILURE.METADATA, 'share2 is invalid');
  }
  const share2 = Buffer.from(share2Encoded, 'base64url');
  if (share2.length !== 32 || share2.toString('base64url') !== share2Encoded) {
    contract(FAILURE.METADATA, 'share2 is invalid');
  }
  const share0 = Buffer.from(share0Text.slice(4), 'hex');
  const ikm = Buffer.alloc(32);
  for (let index = 0; index < ikm.length; index += 1) {
    ikm[index] = share0[index] ^ share1[index] ^ share2[index];
  }
  return {
    ikm,
    shareDigests: [share0, share1, share2]
      .map((share) => createHash('sha256').update(share).digest('hex')),
  };
}

async function verifyKeyAttestation(
  connection,
  job,
  version,
  metadata,
  metadataRevisions,
  workspaceId,
  workPool,
  shareDigests,
) {
  const key = `pfseal.key.v${version}.attestation`;
  const text = metadata.get(key);
  if (typeof text !== 'string' || !metadataRevisions.has(key)) {
    contract(FAILURE.METADATA, 'key-set attestation metadata is missing');
  }
  let attestation;
  try {
    attestation = JSON.parse(text);
  } catch {
    contract(FAILURE.ATTESTATION, 'key-set attestation is invalid JSON');
  }
  if (attestation === null || Array.isArray(attestation) || typeof attestation !== 'object'
      || canonicalJson(attestation) !== text
      || JSON.stringify(Object.keys(attestation).sort()) !== '["revision","signatures"]'
      || !Number.isSafeInteger(attestation.revision) || attestation.revision < 0
      || attestation.revision !== metadataRevisions.get(key)
      || !Array.isArray(attestation.signatures)
      || attestation.signatures.length < KEY_ATTESTATION_THRESHOLD
      || attestation.signatures.length > 3) {
    contract(FAILURE.ATTESTATION, 'key-set attestation is malformed');
  }
  let priorWitness = null;
  const parsed = [];
  for (const entry of attestation.signatures) {
    if (entry === null || Array.isArray(entry) || typeof entry !== 'object'
        || JSON.stringify(Object.keys(entry).sort()) !== '["signature","witnessId"]'
        || typeof entry.witnessId !== 'string' || !WITNESS_ID.test(entry.witnessId)
        || (priorWitness !== null && entry.witnessId <= priorWitness)
        || typeof entry.signature !== 'string') {
      contract(FAILURE.ATTESTATION, 'key-set witness entry is malformed');
    }
    const signature = canonicalBase64(entry.signature, 64);
    if (!signature) contract(FAILURE.ATTESTATION, 'witness signature is malformed');
    priorWitness = entry.witnessId;
    parsed.push({ witnessId: entry.witnessId, signature });
  }

  const statement = {
    deploymentId: job.deploymentId,
    keyVersion: version,
    revision: attestation.revision,
    shareDigests,
    workPool,
    workspaceId,
  };
  const signed = Buffer.from(`PFSEAL2-KEYSET-V1\n${canonicalJson(statement)}`, 'utf8');
  const witnessRows = await readRows(connection, `
    SELECT witness_id, public_key_spki_b64, valid_from_revision,
           valid_through_revision, revoked_at_revision
      FROM pfseal_key_witnesses
     WHERE deployment_id = $deployment_id
  `, { deployment_id: job.deploymentId });
  const witnesses = new Map(witnessRows.map((row) => [row.witness_id, row]));
  let valid = 0;
  for (const entry of parsed) {
    const witness = witnesses.get(entry.witnessId);
    if (!witness) contract(FAILURE.ATTESTATION, 'witness trust root is missing');
    const validFrom = safeUnsigned(witness.valid_from_revision, 'valid_from_revision');
    const validThrough = safeUnsigned(witness.valid_through_revision, 'valid_through_revision');
    const revokedAt = witness.revoked_at_revision === null
      ? null
      : safeUnsigned(witness.revoked_at_revision, 'revoked_at_revision');
    if (validFrom > validThrough || attestation.revision < validFrom
        || attestation.revision > validThrough
        || (revokedAt !== null && revokedAt <= attestation.revision)) {
      contract(FAILURE.ATTESTATION, 'witness is not eligible at the attestation revision');
    }
    const publicDer = canonicalBase64(witness.public_key_spki_b64);
    if (!publicDer) contract(FAILURE.ATTESTATION, 'witness public key is malformed');
    let publicKey;
    try {
      publicKey = createPublicKey({ key: publicDer, format: 'der', type: 'spki' });
    } catch {
      contract(FAILURE.ATTESTATION, 'witness public key is malformed');
    }
    if (publicKey.asymmetricKeyType !== 'ed25519'
        || !verifySignature(null, signed, publicKey, entry.signature)) {
      contract(FAILURE.ATTESTATION, 'witness signature does not authenticate');
    }
    valid += 1;
  }
  if (valid < KEY_ATTESTATION_THRESHOLD) {
    contract(FAILURE.ATTESTATION, 'key-set attestation quorum is not satisfied');
  }
  return createHash('sha256').update(Buffer.from(text, 'utf8')).digest('hex');
}

async function loadKeyContext(connection, job, version) {
  const deployments = await readRows(connection, `
    SELECT active_key_version, minimum_readable_key_version,
           valid_from_revision, valid_through_revision
      FROM prefect_deployments
     WHERE deployment_id = $deployment_id
  `, { deployment_id: job.deploymentId });
  if (deployments.length !== 1) contract(FAILURE.METADATA, 'deployment policy is missing');
  const deployment = deployments[0];
  const activeVersion = Number(deployment.active_key_version);
  const minimumVersion = Number(deployment.minimum_readable_key_version);
  const validFrom = safeUnsigned(deployment.valid_from_revision, 'valid_from_revision');
  const validThrough = safeUnsigned(deployment.valid_through_revision, 'valid_through_revision');
  if (activeVersion < 1 || minimumVersion < 1 || minimumVersion > activeVersion
      || validFrom > validThrough || job.metadataRevision < validFrom
      || job.metadataRevision > validThrough) {
    contract(FAILURE.METADATA, 'deployment policy is inconsistent');
  }

  const metadataRows = await readRows(connection, `
    SELECT metadata_key, metadata_value, revision
      FROM (
        SELECT metadata_key, metadata_value, revision,
               row_number() OVER (PARTITION BY metadata_key ORDER BY revision DESC) AS position
          FROM prefect_deployment_metadata
         WHERE deployment_id = $deployment_id
           AND revision <= $revision
      ) AS effective
     WHERE position = 1
  `, {
    deployment_id: job.deploymentId,
    revision: BigInt(job.metadataRevision),
  });
  const metadata = new Map(metadataRows.map((row) => [row.metadata_key, row.metadata_value]));
  const metadataRevisions = new Map(metadataRows.map((row) => [
    row.metadata_key,
    safeUnsigned(row.revision, 'metadata_revision'),
  ]));
  const workspaceId = metadata.get('prefect.workspace-id');
  const workPool = metadata.get('prefect.work-pool');
  if (typeof workspaceId !== 'string' || typeof workPool !== 'string') {
    contract(FAILURE.METADATA, 'Prefect identity metadata is missing');
  }
  const decodedShares = decodeShares(metadata, version);
  const keyAttestationSha256 = await verifyKeyAttestation(
    connection,
    job,
    version,
    metadata,
    metadataRevisions,
    workspaceId,
    workPool,
    decodedShares.shareDigests,
  );
  const salt = createHash('sha256')
    .update(Buffer.from(`PFSEAL2\0${workspaceId}\0${workPool}`, 'utf8'))
    .digest();
  const info = Buffer.from(
    `prefect-seal/deployment/${job.deploymentId}/key/${version}`,
    'utf8',
  );
  const output = Buffer.from(hkdfSync('sha256', decodedShares.ikm, salt, info, 64));
  return {
    activeVersion,
    minimumVersion,
    encKey: output.subarray(0, 32),
    macKey: output.subarray(32, 64),
    keyAttestationSha256,
    successorProof: metadata.get(`pfseal.key.v${version}.successor`),
  };
}

function verifyLineage(keys, job, version) {
  const expectedPrefix = `v${keys.activeVersion}:`;
  if (typeof keys.successorProof !== 'string'
      || !keys.successorProof.startsWith(expectedPrefix)
      || !/^[0-9a-f]{64}$/.test(keys.successorProof.slice(expectedPrefix.length))) {
    contract(FAILURE.LINEAGE, 'successor proof is malformed');
  }
  const message = Buffer.from(
    `PFSEAL2-ROTATE\0${job.deploymentId}\0${version}\0${keys.activeVersion}\0${job.metadataRevision}`,
    'utf8',
  );
  const expected = createHmac('sha256', keys.macKey).update(message).digest();
  const supplied = Buffer.from(keys.successorProof.slice(expectedPrefix.length), 'hex');
  if (supplied.length !== expected.length || !timingSafeEqual(supplied, expected)) {
    contract(FAILURE.LINEAGE, 'successor proof does not authenticate');
  }
}

function decryptAndValidate(envelope, keys, job, options) {
  const expectedMac = createHmac('sha256', keys.macKey).update(envelope.headerCore).digest();
  if (expectedMac.length !== envelope.headerMac.length
      || !timingSafeEqual(expectedMac, envelope.headerMac)) {
    contract(FAILURE.HEADER, 'header authentication failed');
  }
  let plaintext;
  try {
    const decipher = createDecipheriv('aes-256-gcm', keys.encKey, envelope.nonce, {
      authTagLength: 16,
    });
    decipher.setAAD(envelope.header);
    decipher.setAuthTag(envelope.tag);
    plaintext = Buffer.concat([decipher.update(envelope.ciphertext), decipher.final()]);
  } catch {
    contract(FAILURE.TAG, 'GCM authentication failed');
  }

  let text;
  let payload;
  try {
    text = new TextDecoder('utf-8', { fatal: true }).decode(plaintext);
    payload = JSON.parse(text);
  } catch {
    contract(FAILURE.PAYLOAD, 'payload is not valid UTF-8 JSON');
  }
  if (payload === null || Array.isArray(payload) || typeof payload !== 'object') {
    contract(FAILURE.PAYLOAD, 'payload is not an object');
  }
  if (canonicalJson(payload) !== text
      || JSON.stringify(Object.keys(payload).sort()) !== JSON.stringify(PAYLOAD_KEYS)) {
    contract(FAILURE.PAYLOAD, 'payload is not canonical');
  }
  if (typeof payload.deploymentId !== 'string' || payload.deploymentId !== job.deploymentId
      || typeof payload.issuedAt !== 'string' || !normalizeTimestamp(payload.issuedAt)
      || typeof payload.notBefore !== 'string' || !normalizeTimestamp(payload.notBefore)
      || typeof payload.expiresAt !== 'string' || !normalizeTimestamp(payload.expiresAt)
      || !Number.isSafeInteger(payload.rotationCounter) || payload.rotationCounter < 0
      || typeof payload.secretName !== 'string' || !SECRET_NAME.test(payload.secretName)
      || typeof payload.value !== 'string') {
    contract(FAILURE.PAYLOAD, 'payload fields are invalid');
  }
  const issuedAt = new Date(payload.issuedAt).valueOf();
  const notBefore = new Date(payload.notBefore).valueOf();
  const expiresAt = new Date(payload.expiresAt).valueOf();
  const effectiveAt = new Date(options.at).valueOf();
  if (issuedAt > notBefore || notBefore >= expiresAt) {
    contract(FAILURE.PAYLOAD, 'payload timestamp order is invalid');
  }
  if (effectiveAt < notBefore) {
    contract(FAILURE.NOT_YET_VALID, 'payload is not yet valid');
  }
  if (effectiveAt >= expiresAt) {
    contract(FAILURE.EXPIRED, 'payload has expired');
  }
  return {
    secretName: payload.secretName,
    rotationCounter: payload.rotationCounter,
    plaintextSha256: createHash('sha256').update(plaintext).digest('hex'),
  };
}

async function processJob(connection, job, options) {
  if (typeof job.labelsJson !== 'string') {
    contract(FAILURE.ENVELOPE, 'image row is missing');
  }
  const envelope = parseEnvelopeLabel(job.labelsJson);
  const keys = await loadKeyContext(connection, job, envelope.keyVersion);
  const decision = rotationDecision(
    envelope.keyVersion,
    keys.activeVersion,
    keys.minimumVersion,
  );
  if (decision === 'retired') contract(FAILURE.RETIRED, 'key is retired');
  if (decision === 'future') contract(FAILURE.FUTURE, 'key is from the future');
  if (decision === 'rotate') verifyLineage(keys, job, envelope.keyVersion);
  const payload = decryptAndValidate(envelope, keys, job, options);
  const states = await readRows(connection, `
    SELECT last_rotation_counter
      FROM prefect_secret_state
     WHERE deployment_id = $deployment_id AND secret_name = $secret_name
  `, { deployment_id: job.deploymentId, secret_name: payload.secretName });
  if (states.length > 1) throw new Error('duplicate replay state');
  if (states.length === 1
      && payload.rotationCounter <= safeUnsigned(states[0].last_rotation_counter, 'last_rotation_counter')) {
    contract(FAILURE.REPLAY, 'payload rotation counter was already consumed');
  }
  return {
    decision,
    keyVersion: envelope.keyVersion,
    activeVersion: keys.activeVersion,
    headerSha256: createHash('sha256').update(envelope.header).digest('hex'),
    keyAttestationSha256: keys.keyAttestationSha256,
    ...payload,
  };
}

function unsigned16(value) {
  const bytes = Buffer.alloc(2);
  bytes.writeUInt16BE(value);
  return bytes;
}

function unsigned64(value) {
  const bytes = Buffer.alloc(8);
  bytes.writeBigUInt64BE(BigInt(value));
  return bytes;
}

function transparencyMerkleRoot(heads) {
  if (heads.length === 0) throw new Error('transparency tree is empty');
  const normalized = heads.map((head) => {
    if (typeof head.deploymentId !== 'string') {
      throw new Error('audit-head deployment id is invalid');
    }
    const deploymentBytes = Buffer.from(head.deploymentId, 'utf8');
    if (deploymentBytes.length < 1 || deploymentBytes.length > 65535) {
      throw new Error('audit-head deployment id is invalid');
    }
    const sequence = safeUnsigned(head.sequence, 'audit head sequence');
    if (sequence < 1
        || typeof head.auditHash !== 'string'
        || !/^[0-9a-f]{64}$/.test(head.auditHash)) {
      throw new Error('audit head is invalid');
    }
    return { ...head, deploymentBytes, sequence };
  });
  normalized.sort((left, right) => Buffer.compare(left.deploymentBytes, right.deploymentBytes));
  let level = normalized.map((head) => createHash('sha256').update(Buffer.concat([
    Buffer.from([0]),
    unsigned16(head.deploymentBytes.length),
    head.deploymentBytes,
    unsigned64(head.sequence),
    Buffer.from(head.auditHash, 'hex'),
  ])).digest());
  while (level.length > 1) {
    if (level.length % 2 === 1) level.push(level[level.length - 1]);
    const parentLevel = [];
    for (let index = 0; index < level.length; index += 2) {
      parentLevel.push(createHash('sha256').update(Buffer.concat([
        Buffer.from([1]), level[index], level[index + 1],
      ])).digest());
    }
    level = parentLevel;
  }
  return level[0].toString('hex');
}

function bagEventPeaks(peaks) {
  const ordered = [...peaks].reverse().filter((peak) => peak !== null);
  if (ordered.length === 0) throw new Error('event frontier is empty');
  let root = Buffer.from(ordered[0], 'hex');
  for (const peak of ordered.slice(1)) {
    root = createHash('sha256').update(Buffer.concat([
      Buffer.from([4]), root, Buffer.from(peak, 'hex'),
    ])).digest();
  }
  return root.toString('hex');
}

function parseEventFrontier(row, sequence) {
  if (typeof row.frontier_json !== 'string') {
    throw new Error('checkpoint frontier is invalid');
  }
  let peaks;
  try {
    peaks = JSON.parse(row.frontier_json);
  } catch {
    throw new Error('checkpoint frontier is invalid');
  }
  const bits = BigInt(sequence);
  const expectedLength = bits.toString(2).length;
  if (!Array.isArray(peaks) || peaks.length !== expectedLength
      || canonicalJson(peaks) !== row.frontier_json) {
    throw new Error('checkpoint frontier is invalid');
  }
  for (let height = 0; height < peaks.length; height += 1) {
    const present = ((bits >> BigInt(height)) & 1n) === 1n;
    if ((present && (typeof peaks[height] !== 'string'
          || !/^[0-9a-f]{64}$/.test(peaks[height])))
        || (!present && peaks[height] !== null)) {
      throw new Error('checkpoint frontier is invalid');
    }
  }
  const frontierSha256 = createHash('sha256')
    .update(Buffer.from(row.frontier_json, 'utf8'))
    .digest('hex');
  if (typeof row.frontier_sha256 !== 'string'
      || row.frontier_sha256 !== frontierSha256
      || typeof row.event_mmr_root !== 'string'
      || !/^[0-9a-f]{64}$/.test(row.event_mmr_root)
      || bagEventPeaks(peaks) !== row.event_mmr_root) {
    throw new Error('checkpoint frontier is invalid');
  }
  return peaks;
}

function appendEventFrontier(
  priorPeaks,
  checkpointSequence,
  jobId,
  merkleRoot,
  triggeringAuditHash,
) {
  let carry = createHash('sha256').update(Buffer.concat([
    Buffer.from([2]),
    unsigned64(checkpointSequence),
    unsigned64(jobId),
    Buffer.from(merkleRoot, 'hex'),
    Buffer.from(triggeringAuditHash, 'hex'),
  ])).digest();
  const peaks = [...priorPeaks];
  let height = 0;
  while (height < peaks.length && peaks[height] !== null) {
    carry = createHash('sha256').update(Buffer.concat([
      Buffer.from([3]), Buffer.from(peaks[height], 'hex'), carry,
    ])).digest();
    peaks[height] = null;
    height += 1;
  }
  if (height === peaks.length) peaks.push(carry.toString('hex'));
  else peaks[height] = carry.toString('hex');
  const frontierJson = canonicalJson(peaks);
  return {
    frontierJson,
    frontierSha256: createHash('sha256')
      .update(Buffer.from(frontierJson, 'utf8'))
      .digest('hex'),
    eventMmrRoot: bagEventPeaks(peaks),
  };
}

async function buildTransparencyCheckpoint(
  connection,
  options,
  job,
  auditSequence,
  auditHash,
) {
  const persistedHeads = await readRows(connection, `
    SELECT deployment_id, last_sequence, last_audit_hash
      FROM pfseal_audit_heads
  `);
  const prospective = new Map();
  for (const head of persistedHeads) {
    if (prospective.has(head.deployment_id)) throw new Error('duplicate audit head');
    prospective.set(head.deployment_id, {
      deploymentId: head.deployment_id,
      sequence: head.last_sequence,
      auditHash: head.last_audit_hash,
    });
  }
  prospective.set(job.deploymentId, {
    deploymentId: job.deploymentId,
    sequence: auditSequence,
    auditHash,
  });
  const merkleRoot = transparencyMerkleRoot([...prospective.values()]);

  const priorRows = await readRows(connection, `
    SELECT checkpoint_sequence, checkpoint_hash, event_mmr_root,
           frontier_json, frontier_sha256
      FROM pfseal_transparency_checkpoints
     ORDER BY checkpoint_sequence DESC
     LIMIT 1
  `);
  let checkpointSequence = 1;
  let previousCheckpointHash = ZERO_HASH;
  let previousEventMmrRoot = ZERO_HASH;
  let priorPeaks = [];
  if (priorRows.length === 1) {
    const priorSequence = safeUnsigned(
      priorRows[0].checkpoint_sequence,
      'checkpoint_sequence',
    );
    if (priorSequence < 1 || priorSequence >= Number.MAX_SAFE_INTEGER
        || typeof priorRows[0].checkpoint_hash !== 'string'
        || !/^[0-9a-f]{64}$/.test(priorRows[0].checkpoint_hash)) {
      throw new Error('checkpoint head is invalid');
    }
    checkpointSequence = priorSequence + 1;
    previousCheckpointHash = priorRows[0].checkpoint_hash;
    priorPeaks = parseEventFrontier(priorRows[0], priorSequence);
    previousEventMmrRoot = priorRows[0].event_mmr_root;
  }
  const eventState = appendEventFrontier(
    priorPeaks,
    checkpointSequence,
    job.jobId,
    merkleRoot,
    auditHash,
  );
  const checkpointRecord = {
    checkpointSequence,
    eventMmrRoot: eventState.eventMmrRoot,
    frontierSha256: eventState.frontierSha256,
    headCount: prospective.size,
    jobId: job.jobId,
    merkleRoot,
    previousCheckpointHash,
    previousEventMmrRoot,
    processedAt: options.at,
    triggeringAuditHash: auditHash,
  };
  const checkpointHash = createHash('sha256')
    .update(Buffer.from(
      `PFSEAL-CHECKPOINT-V1\n${canonicalJson(checkpointRecord)}`,
      'utf8',
    ))
    .digest('hex');
  return {
    checkpointSequence,
    headCount: prospective.size,
    merkleRoot,
    previousCheckpointHash,
    previousEventMmrRoot,
    ...eventState,
    checkpointHash,
  };
}

async function finalizeSuccess(connection, options, job, result) {
  await begin(connection);
  try {
    const states = await readRows(connection, `
      SELECT last_rotation_counter
        FROM prefect_secret_state
       WHERE deployment_id = $deployment_id AND secret_name = $secret_name
    `, { deployment_id: job.deploymentId, secret_name: result.secretName });
    if (states.length > 1) throw new Error('duplicate replay state');
    if (states.length === 1
        && result.rotationCounter <= safeUnsigned(
          states[0].last_rotation_counter,
          'last_rotation_counter',
        )) {
      contract(FAILURE.REPLAY, 'payload rotation counter was already consumed');
    }

    const heads = await readRows(connection, `
      SELECT last_sequence, last_audit_hash
        FROM pfseal_audit_heads
       WHERE deployment_id = $deployment_id
    `, { deployment_id: job.deploymentId });
    if (heads.length > 1) throw new Error('duplicate audit head');
    let auditSequence = 1;
    let previousAuditHash = ZERO_HASH;
    if (heads.length === 1) {
      const lastSequence = safeUnsigned(heads[0].last_sequence, 'last_sequence');
      if (lastSequence >= Number.MAX_SAFE_INTEGER
          || typeof heads[0].last_audit_hash !== 'string'
          || !/^[0-9a-f]{64}$/.test(heads[0].last_audit_hash)) {
        throw new Error('audit head is invalid');
      }
      auditSequence = lastSequence + 1;
      previousAuditHash = heads[0].last_audit_hash;
    }
    const auditRecord = {
      activeKeyVersion: result.activeVersion,
      auditSequence,
      deploymentId: job.deploymentId,
      envelopeKeyVersion: result.keyVersion,
      headerSha256: result.headerSha256,
      imageDigest: job.imageDigest,
      jobId: job.jobId,
      keyAttestationSha256: result.keyAttestationSha256,
      metadataRevision: job.metadataRevision,
      plaintextSha256: result.plaintextSha256,
      previousAuditHash,
      processedAt: options.at,
      rotationCounter: result.rotationCounter,
      rotationDecision: result.decision,
      secretName: result.secretName,
      workerId: options.workerId,
    };
    const auditHash = createHash('sha256')
      .update(Buffer.from(`PFSEAL-AUDIT-V1\n${canonicalJson(auditRecord)}`, 'utf8'))
      .digest('hex');
    const checkpoint = await buildTransparencyCheckpoint(
      connection,
      options,
      job,
      auditSequence,
      auditHash,
    );

    await connection.run(`
      INSERT INTO pfseal_audit (
        job_id, deployment_id, image_digest, envelope_key_version,
        active_key_version, metadata_revision, key_attestation_sha256, header_sha256,
        plaintext_sha256, secret_name, rotation_counter, rotation_decision,
        audit_sequence, previous_audit_hash, audit_hash, worker_id, processed_at
      ) VALUES (
        $job_id, $deployment_id, $image_digest, $key_version,
        $active_version, $metadata_revision, $key_attestation_sha256, $header_sha256,
        $plaintext_sha256, $secret_name, $rotation_counter, $decision,
        $audit_sequence, $previous_audit_hash, $audit_hash,
        $worker_id, CAST($processed_at AS TIMESTAMP)
      )
    `, {
      job_id: BigInt(job.jobId),
      deployment_id: job.deploymentId,
      image_digest: job.imageDigest,
      key_version: result.keyVersion,
      active_version: result.activeVersion,
      metadata_revision: BigInt(job.metadataRevision),
      key_attestation_sha256: result.keyAttestationSha256,
      header_sha256: result.headerSha256,
      plaintext_sha256: result.plaintextSha256,
      secret_name: result.secretName,
      rotation_counter: BigInt(result.rotationCounter),
      decision: result.decision,
      audit_sequence: BigInt(auditSequence),
      previous_audit_hash: previousAuditHash,
      audit_hash: auditHash,
      worker_id: options.workerId,
      processed_at: options.at,
    });
    await connection.run(`
      INSERT INTO pfseal_audit_heads VALUES ($deployment_id, $sequence, $audit_hash)
      ON CONFLICT (deployment_id) DO UPDATE
        SET last_sequence = EXCLUDED.last_sequence,
            last_audit_hash = EXCLUDED.last_audit_hash
    `, {
      deployment_id: job.deploymentId,
      sequence: BigInt(auditSequence),
      audit_hash: auditHash,
    });
    await connection.run(`
      INSERT INTO pfseal_transparency_checkpoints (
        checkpoint_sequence, job_id, head_count, merkle_root,
        triggering_audit_hash, previous_checkpoint_hash, previous_event_mmr_root,
        event_mmr_root, frontier_json, frontier_sha256, checkpoint_hash, created_at
      ) VALUES (
        $checkpoint_sequence, $job_id, $head_count, $merkle_root,
        $triggering_audit_hash, $previous_checkpoint_hash, $previous_event_mmr_root,
        $event_mmr_root, $frontier_json, $frontier_sha256, $checkpoint_hash,
        CAST($created_at AS TIMESTAMP)
      )
    `, {
      checkpoint_sequence: BigInt(checkpoint.checkpointSequence),
      job_id: BigInt(job.jobId),
      head_count: BigInt(checkpoint.headCount),
      merkle_root: checkpoint.merkleRoot,
      triggering_audit_hash: auditHash,
      previous_checkpoint_hash: checkpoint.previousCheckpointHash,
      previous_event_mmr_root: checkpoint.previousEventMmrRoot,
      event_mmr_root: checkpoint.eventMmrRoot,
      frontier_json: checkpoint.frontierJson,
      frontier_sha256: checkpoint.frontierSha256,
      checkpoint_hash: checkpoint.checkpointHash,
      created_at: options.at,
    });
    await connection.run(`
      INSERT INTO prefect_secret_state VALUES (
        $deployment_id, $secret_name, $rotation_counter, $plaintext_sha256,
        CAST($updated_at AS TIMESTAMP)
      )
      ON CONFLICT (deployment_id, secret_name) DO UPDATE
        SET last_rotation_counter = EXCLUDED.last_rotation_counter,
            last_plaintext_sha256 = EXCLUDED.last_plaintext_sha256,
            updated_at = EXCLUDED.updated_at
    `, {
      deployment_id: job.deploymentId,
      secret_name: result.secretName,
      rotation_counter: BigInt(result.rotationCounter),
      plaintext_sha256: result.plaintextSha256,
      updated_at: options.at,
    });
    if (result.decision === 'rotate') {
      await connection.run(`
        INSERT INTO pfseal_rotation_outbox (
          job_id, deployment_id, secret_name, from_key_version,
          to_key_version, enqueued_at
        ) VALUES (
          $job_id, $deployment_id, $secret_name, $from_version,
          $to_version, CAST($enqueued_at AS TIMESTAMP)
        )
      `, {
        job_id: BigInt(job.jobId),
        deployment_id: job.deploymentId,
        secret_name: result.secretName,
        from_version: result.keyVersion,
        to_version: result.activeVersion,
        enqueued_at: options.at,
      });
    }
    await connection.run(`
      UPDATE prefect_secret_jobs
         SET status = 'succeeded', completed_at = CAST($completed_at AS TIMESTAMP),
             lease_owner = NULL, lease_until = NULL, failure_code = NULL
       WHERE job_id = $job_id
    `, { completed_at: options.at, job_id: BigInt(job.jobId) });
    await connection.run('COMMIT');
  } catch (error) {
    await rollback(connection);
    throw error;
  }
}

async function finalizeFailure(connection, options, job, code) {
  await begin(connection);
  try {
    await connection.run(`
      UPDATE prefect_secret_jobs
         SET status = 'failed', completed_at = CAST($completed_at AS TIMESTAMP),
             lease_owner = NULL, lease_until = NULL, failure_code = $failure_code
       WHERE job_id = $job_id
    `, {
      completed_at: options.at,
      failure_code: code,
      job_id: BigInt(job.jobId),
    });
    await connection.run('COMMIT');
  } catch (error) {
    await rollback(connection);
    throw error;
  }
}

function emptySummary(workerId) {
  return {
    workerId,
    claimed: 0,
    succeeded: 0,
    failed: 0,
    rotations: 0,
    jobs: [],
  };
}

export async function runWorker(options) {
  const instance = await DuckDBInstance.create(options.db);
  const connection = await instance.connect();
  const summary = emptySummary(options.workerId);
  let stopRequested = false;
  let wakePoll = null;
  const requestStop = () => {
    stopRequested = true;
    if (wakePoll) wakePoll();
  };
  process.once('SIGINT', requestStop);
  process.once('SIGTERM', requestStop);
  let emptyPolls = 0;
  try {
    while (!stopRequested) {
      const job = await claimNext(connection, options);
      if (job === null) {
        emptyPolls += 1;
        if (options.once || (options.idleLimit > 0 && emptyPolls >= options.idleLimit)) break;
        await new Promise((resolve) => {
          wakePoll = resolve;
          const timer = setTimeout(resolve, options.pollMs);
          const prior = wakePoll;
          wakePoll = () => {
            clearTimeout(timer);
            prior();
          };
        });
        wakePoll = null;
        continue;
      }
      emptyPolls = 0;
      summary.claimed += 1;
      try {
        const result = await processJob(connection, job, options);
        await finalizeSuccess(connection, options, job, result);
        summary.succeeded += 1;
        if (result.decision === 'rotate') summary.rotations += 1;
        summary.jobs.push({
          jobId: job.jobId,
          status: 'succeeded',
          decision: result.decision,
        });
      } catch (error) {
        if (!(error instanceof ContractError)) throw error;
        await finalizeFailure(connection, options, job, error.code);
        summary.failed += 1;
        summary.jobs.push({
          jobId: job.jobId,
          status: 'failed',
          error: error.code,
        });
      }
    }
    return summary;
  } finally {
    process.removeListener('SIGINT', requestStop);
    process.removeListener('SIGTERM', requestStop);
    connection.closeSync();
    instance.closeSync();
  }
}
EOF

chmod 0755 "${app_root}/bin/pfseal-worker"
