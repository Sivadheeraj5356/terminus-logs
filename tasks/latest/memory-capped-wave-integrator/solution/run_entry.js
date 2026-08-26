const fs = require('fs');
const path = require('path');

const opA = require('./base/src/op_' + 'a.js')['op_' + 'a'];
const phaseB = require('./core/src/phase_' + 'b.js')['phase_' + 'b'];
const reconcileC = require('./util/src/reconcile_' + 'c.js')['reconcile_' + 'c'];

const configPath = process.argv[2] || path.join(__dirname, 'config', 'defaults.json');
const outputPath = process.argv[3] || '/app/output_trace.json';

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

// CFL Check
const cflFactor = order === 2 ? 1.0 : Math.sqrt(3/7);
const dtMax = (dx / (c * Math.sqrt(2))) * cflFactor;
if (dt > dtMax) {
    console.error(`CFL stability condition violated: dt (${dt}) exceeds dtMax (${dtMax}) for order ${order}`);
    process.exit(1);
}

// Load source pulse
const sourcePath = path.join(__dirname, 'fixtures', 'source_layout.json');
const sourceLayout = JSON.parse(fs.readFileSync(sourcePath, 'utf8'));
const pulse = sourceLayout.pulse;

// Load halo mask
const haloPath = path.join(__dirname, 'fixtures', 'halo_configuration.json');
const haloConfig = JSON.parse(fs.readFileSync(haloPath, 'utf8'));

// Initialize buffers
const buffers = opA(gridSize, 2);

// Set initial conditions
const initPulse = () => {
    // Initialize indices
    const { curr, prev, width, ghost } = buffers;
    for (let i = 0; i < gridSize; i++) {
        const row = (i + ghost) * width;
        for (let j = 0; j < gridSize; j++) {
            const dist2 = Math.pow(i - pulse.centerX, 2) + Math.pow(j - pulse.centerY, 2);
            const val = pulse.amplitude * Math.exp(-dist2 / (2 * Math.pow(pulse.sigma, 2)));
            const idx = row + ghost + j;
            curr[idx] = val;
            prev[idx] = val;
        }
    }
};
initPulse();

// Apply initial boundaries
reconcileC(buffers, haloConfig, order);

let maxMemoryBytes = 0;
const traces = [];

// Helper to extract interior grid for trace
const getInteriorGrid = (buf) => {
    const { curr, width, ghost } = buf;
    const arr = [];
    for (let i = 0; i < gridSize; i++) {
        const row = (i + ghost) * width;
        for (let j = 0; j < gridSize; j++) {
            arr.push(curr[row + ghost + j]);
        }
    }
    return arr;
};

// Stride 0 trace
if (0 % stride === 0) {
    // Store trace step
    traces.push({
        step: 0,
        t: 0.0,
        grid: getInteriorGrid(buffers)
    });
}

// Time loop
for (let step = 1; step <= steps; step++) {
    // Stencil update
    phaseB(buffers, dt, dx, order);
    
    // Apply boundaries
    reconcileC(buffers, haloConfig, order);
    
    // swap buffers
    const tmp = buffers.prev;
    buffers.prev = buffers.curr;
    buffers.curr = buffers.next;
    buffers.next = tmp;
    
    // Monitor memory
    const mem = process.memoryUsage().heapUsed;
    if (mem > maxMemoryBytes) {
        maxMemoryBytes = mem;
    }
    
    // Trace
    if (step % stride === 0) {
        // Store trace step
        traces.push({
            step,
            t: step * dt,
            grid: getInteriorGrid(buffers)
        });
    }
}

// Output final trace JSON
const outputData = {
    gridSize,
    steps,
    stride,
    order,
    traces,
    maxMemoryBytes
};

fs.writeFileSync(outputPath, JSON.stringify(outputData, null, 2));
console.log(`Simulation finished successfully. Trace written to ${outputPath}`);
