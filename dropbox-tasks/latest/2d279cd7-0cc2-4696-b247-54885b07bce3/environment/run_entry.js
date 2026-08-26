const fs = require('fs');
const path = require('path');

const opA = require('./base/src/op_' + 'a.js')['op_' + 'a'];
const phaseB = require('./core/src/phase_' + 'b.js')['phase_' + 'b'];
const reconcileC = require('./util/src/reconcile_' + 'c.js')['reconcile_' + 'c'];
const sampleD = require('./trace/src/sample_' + 'd.js')['sample_' + 'd'];

const CKPT_MAGIC = Buffer.from([0x57, 0x4A, 0x43, 0x4B]);
const CKPT_VERSION = 1;
const CKPT_EPOCH = 1;

function parseArgs(argv) {
    const positional = [];
    let checkpointPath = null;
    let resume = false;
    for (let i = 2; i < argv.length; i++) {
        if (argv[i] === '--checkpoint' && i + 1 < argv.length) {
            checkpointPath = argv[++i];
        } else if (argv[i] === '--resume') {
            resume = true;
        } else {
            positional.push(argv[i]);
        }
    }
    return { positional, checkpointPath, resume };
}

function fnv1a64(buf) {
    let hash = BigInt('14695981039346656037');
    const prime = BigInt('1099511628211');
    for (let i = 0; i < buf.length; i++) {
        hash ^= BigInt(buf[i]);
        hash = (hash * prime) & BigInt('0xFFFFFFFFFFFFFFFF');
    }
    return hash;
}

function paddedWidth(gridSize) {
    return gridSize + 4;
}

function writeCheckpoint(filePath, buffers, step, gridSize, order) {
    const W = paddedWidth(gridSize);
    const payloadLen = 2 * W * W * 8;
    const header = Buffer.alloc(32);
    CKPT_MAGIC.copy(header, 0);
    header.writeUInt32LE(CKPT_VERSION, 4);
    header.writeUInt32LE(step, 8);
    header.writeUInt32LE(CKPT_EPOCH, 12);
    header.writeUInt32LE(gridSize, 16);
    header.writeUInt32LE(order, 20);
    const prevBuf = Buffer.from(buffers.prev.buffer, buffers.prev.byteOffset, buffers.prev.byteLength);
    const currBuf = Buffer.from(buffers.curr.buffer, buffers.curr.byteOffset, buffers.curr.byteLength);
    const payload = Buffer.concat([prevBuf, currBuf]);
    const checksum = fnv1a64(payload);
    header.writeBigUInt64LE(checksum, 24);
    fs.writeFileSync(filePath, Buffer.concat([header, payload]));
}

function loadCheckpoint(filePath, gridSize, order) {
    const data = fs.readFileSync(filePath);
    if (data.length < 32) {
        console.error('checksum: truncated checkpoint');
        process.exit(1);
    }
    if (!data.subarray(0, 4).equals(CKPT_MAGIC)) {
        console.error('checksum: invalid magic');
        process.exit(1);
    }
    const version = data.readUInt32LE(4);
    if (version !== CKPT_VERSION) {
        console.error('epoch: unsupported version');
        process.exit(1);
    }
    const step = data.readUInt32LE(8);
    const epoch = data.readUInt32LE(12);
    const ckGrid = data.readUInt32LE(16);
    const ckOrder = data.readUInt32LE(20);
    if (ckGrid !== gridSize || ckOrder !== order) {
        console.error('epoch: config mismatch');
        process.exit(1);
    }
    const W = paddedWidth(gridSize);
    const payloadLen = 2 * W * W * 8;
    const payload = data.subarray(32, 32 + payloadLen);
    const expected = data.readBigUInt64LE(24);
    const actual = fnv1a64(payload);
    if (expected !== actual) {
        console.error('checksum: payload mismatch');
        process.exit(1);
    }
    if (epoch !== CKPT_EPOCH) {
        console.error('epoch: stale epoch');
        process.exit(1);
    }
    const prev = new Float64Array(W * W);
    const curr = new Float64Array(W * W);
    prev.set(new Float64Array(payload.buffer, payload.byteOffset, W * W));
    curr.set(new Float64Array(payload.buffer, payload.byteOffset + W * W * 8, W * W));
    return { step, prev, curr };
}

function resolveHaloPath(profile) {
    if (profile === 'mixed') {
        return path.join(__dirname, 'fixtures', 'halo_mixed.json');
    }
    return path.join(__dirname, 'fixtures', 'halo_configuration.json');
}

const { positional, checkpointPath, resume } = parseArgs(process.argv);
const configPath = positional[0] || path.join(__dirname, 'config', 'defaults.json');
const outputPath = positional[1] || '/app/output_trace.json';

if (!fs.existsSync(configPath)) {
    console.error(`Config file not found: ${configPath}`);
    process.exit(1);
}

const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
const gridSize = config.gridSize;
const c = config.c || 1.0;
const dx = config.dx;
const dt = config.dt;
const steps = config.steps;
const stride = config.stride;
const order = config.order;
const haloProfile = config.haloProfile || 'default';

const cflFactor = order === 2 ? 1.0 : Math.sqrt(3 / 7);
const dtMax = (dx / (c * Math.sqrt(2))) * cflFactor;
if (dt > dtMax) {
    console.error(`CFL stability condition violated: dt (${dt}) exceeds dtMax (${dtMax}) for order ${order}`);
    process.exit(1);
}

const sourcePath = path.join(__dirname, 'fixtures', 'source_layout.json');
const sourceLayout = JSON.parse(fs.readFileSync(sourcePath, 'utf8'));
const pulse = sourceLayout.pulse;

const haloPath = resolveHaloPath(haloProfile);
const haloConfig = JSON.parse(fs.readFileSync(haloPath, 'utf8'));

const buffers = opA(gridSize, 2);
let startStep = 0;

if (resume && checkpointPath) {
    const loaded = loadCheckpoint(checkpointPath, gridSize, order);
    buffers.prev.set(loaded.prev);
    buffers.curr.set(loaded.curr);
    startStep = loaded.step;
} else {
    const { curr, prev, width, ghost } = buffers;
    const centerX = gridSize / 2.0;
    const centerY = gridSize / 2.0;
    for (let i = 0; i < gridSize; i++) {
        const row = (i + ghost) * width;
        for (let j = 0; j < gridSize; j++) {
            const dist2 = Math.pow(i - centerX, 2) + Math.pow(j - centerY, 2);
            const val = pulse.amplitude * Math.exp(-dist2 / (2 * Math.pow(pulse.sigma, 2)));
            const idx = row + ghost + j;
            curr[idx] = val;
            prev[idx] = val;
        }
    }
    reconcileC(buffers, haloConfig, order);
}

let maxMemoryBytes = 0;
const traces = [];

if (startStep === 0 && 0 % stride === 0) {
    traces.push(sampleD(buffers, 0, 0.0));
}

for (let step = startStep + 1; step <= steps; step++) {
    phaseB(buffers, dt, dx, order);
    reconcileC(buffers, haloConfig, order);

    const tmp = buffers.prev;
    buffers.prev = buffers.curr;
    buffers.curr = buffers.next;
    buffers.next = tmp;

    if (checkpointPath) {
        writeCheckpoint(checkpointPath, buffers, step, gridSize, order);
    }

    const mem = process.memoryUsage().heapUsed;
    if (mem > maxMemoryBytes) {
        maxMemoryBytes = mem;
    }

    if (step % stride === 0) {
        traces.push(sampleD(buffers, step, step * dt));
    }
}

fs.writeFileSync(outputPath, JSON.stringify({
    gridSize,
    steps,
    stride,
    order,
    maxMemoryBytes,
    traces
}, null, 2));
