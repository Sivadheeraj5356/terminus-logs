// Decoy core updater
// Simple wave update using 1st order differences for testing.

function phase_decoy(buffers, dt, dx) {
    const { prev, curr, next, width, gridSize } = buffers;
    const c = 1.0;
    const factor = (c * dt / dx) * (c * dt / dx);
    for (let i = 1; i < gridSize + 1; i++) {
        for (let j = 1; j < gridSize + 1; j++) {
            const idx = i * width + j;
            const laplacian = curr[idx+1] + curr[idx-1] + curr[idx+width] + curr[idx-width] - 4 * curr[idx];
            next[idx] = 2 * curr[idx] - prev[idx] + factor * laplacian;
        }
    }
}

module.exports = { phase_decoy };
