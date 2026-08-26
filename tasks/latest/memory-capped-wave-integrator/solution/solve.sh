#!/bin/bash

if [ -f "run_entry.js" ]; then
    TARGET_DIR="."
elif [ -f "environment/run_entry.js" ]; then
    TARGET_DIR="environment"
else
    TARGET_DIR="/app"
fi

mkdir -p "$TARGET_DIR/base/src"
mkdir -p "$TARGET_DIR/core/src"
mkdir -p "$TARGET_DIR/util/src"
mkdir -p "$TARGET_DIR/trace/src"

cat > "$TARGET_DIR/base/src/op_a.js" << 'EOF'
function op_a(gridSize, dims) {
    const H = 2;
    const W = gridSize + 2 * H;
    const size = W * W;

    const prev = new Float64Array(size);
    const curr = new Float64Array(size);
    const next = new Float64Array(size);

    return {
        prev,
        curr,
        next,
        width: W,
        height: W,
        gridSize: gridSize,
        ghost: H
    };
}
module.exports = { op_a };
EOF

cat > "$TARGET_DIR/core/src/phase_b.js" << 'EOF'
function phase_b(buffers, dt, dx, order) {
    const { prev, curr, next, width, gridSize, ghost } = buffers;
    const c = 1.0;
    const factor = (c * c) * (dt * dt);
    const dx2 = dx * dx;

    if (order === 2) {
        const coeff = factor / dx2;
        for (let i = ghost; i < gridSize + ghost; i++) {
            const row = i * width;
            for (let j = ghost; j < gridSize + ghost; j++) {
                const idx = row + j;
                const lap = curr[idx + 1] + curr[idx - 1] + curr[idx + width] + curr[idx - width] - 4.0 * curr[idx];
                next[idx] = 2.0 * curr[idx] - prev[idx] + coeff * lap;
            }
        }
    } else if (order === 4) {
        const coeff = factor / (12.0 * dx2);
        for (let i = ghost; i < gridSize + ghost; i++) {
            const row = i * width;
            for (let j = ghost; j < gridSize + ghost; j++) {
                const idx = row + j;
                const lap = -curr[idx + 2] - curr[idx - 2] - curr[idx + 2 * width] - curr[idx - 2 * width]
                    + 16.0 * (curr[idx + 1] + curr[idx - 1] + curr[idx + width] + curr[idx - width])
                    - 60.0 * curr[idx];
                next[idx] = 2.0 * curr[idx] - prev[idx] + coeff * lap;
            }
        }
    }
}
module.exports = { phase_b };
EOF

cat > "$TARGET_DIR/util/src/reconcile_c.js" << 'EOF'
function reconcile_c(buffers, mask, order) {
    const { curr, width, gridSize, ghost } = buffers;
    const N = gridSize;
    const W = width;
    const H = ghost;

    const boundaries = mask.boundaries || {
        left: "dirichlet",
        right: "dirichlet",
        top: "dirichlet",
        bottom: "dirichlet"
    };

    for (let i = 0; i < W; i++) {
        const row = i * W;
        if (boundaries.left === "dirichlet") {
            for (let d = 0; d < H; d++) {
                curr[row + d] = 0;
            }
        } else if (boundaries.left === "neumann") {
            for (let d = 1; d <= H; d++) {
                curr[row + H - d] = curr[row + H + d];
            }
        }
        if (boundaries.right === "dirichlet") {
            for (let d = 0; d < H; d++) {
                curr[row + H + N + d] = 0;
            }
        } else if (boundaries.right === "neumann") {
            for (let d = 1; d <= H; d++) {
                curr[row + H + N - 1 + d] = curr[row + H + N - 1 - d];
            }
        }
    }

    for (let j = 0; j < W; j++) {
        if (boundaries.top === "dirichlet") {
            for (let d = 0; d < H; d++) {
                curr[d * W + j] = 0;
            }
        } else if (boundaries.top === "neumann") {
            for (let d = 1; d <= H; d++) {
                curr[(H - d) * W + j] = curr[(H + d) * W + j];
            }
        }
        if (boundaries.bottom === "dirichlet") {
            for (let d = 0; d < H; d++) {
                curr[(H + N + d) * W + j] = 0;
            }
        } else if (boundaries.bottom === "neumann") {
            for (let d = 1; d <= H; d++) {
                curr[(H + N - 1 + d) * W + j] = curr[(H + N - 1 - d) * W + j];
            }
        }
    }
}
module.exports = { reconcile_c };
EOF

cat > "$TARGET_DIR/trace/src/sample_d.js" << 'EOF'
function sample_d(buffers, step, t) {
    const { curr, width, ghost, gridSize } = buffers;
    const n = gridSize * gridSize;
    const interior = new Float64Array(n);
    let k = 0;
    for (let i = 0; i < gridSize; i++) {
        const row = (i + ghost) * width;
        for (let j = 0; j < gridSize; j++) {
            interior[k++] = curr[row + ghost + j];
        }
    }
    return {
        step: step,
        t: t,
        grid: Array.from(interior)
    };
}
module.exports = { sample_d };
EOF

cat > "$TARGET_DIR/run_entry.js" << 'EOF'
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
    const prevBuf = Buffer.from(buffers.prev.buffer, buffers.prev.byteOffset, buffers.prev.byteLength);
    const currBuf = Buffer.from(buffers.curr.buffer, buffers.curr.byteOffset, buffers.curr.byteLength);
    const payload = Buffer.concat([prevBuf, currBuf]);
    const header = Buffer.alloc(32);
    CKPT_MAGIC.copy(header, 0);
    header.writeUInt32LE(CKPT_VERSION, 4);
    header.writeUInt32LE(step, 8);
    header.writeUInt32LE(CKPT_EPOCH, 12);
    header.writeUInt32LE(gridSize, 16);
    header.writeUInt32LE(order, 20);
    header.writeBigUInt64LE(fnv1a64(payload), 24);
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
    buffers.next.fill(0);
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
    reconcileC(buffers, haloConfig, order);
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
EOF
