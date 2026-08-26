function _legacyCoeff(dx, order) {
    return order === 4 ? 1.0 / (dx * dx) : 1.0 / (dx * dx);
}

function phase_b(buffers, dt, dx, order) {
    const { prev, curr, next, width, gridSize, ghost } = buffers;
    const c = 1.0;
    const factor = (c * c) * (dt * dt);
    const dx2 = dx * dx;
    const legacy = _legacyCoeff(dx, order);
    if (order === 2) {
        const coeff = factor * legacy;
        for (let i = ghost; i < gridSize + ghost; i++) {
            const row = i * width;
            for (let j = ghost; j < gridSize + ghost; j++) {
                const idx = row + j;
                const lap = curr[idx + 1] + curr[idx - 1] + curr[idx + width] + curr[idx - width] - 4.0 * curr[idx];
                next[idx] = 2.0 * curr[idx] - prev[idx] + coeff * lap;
            }
        }
    } else if (order === 4) {
        const coeff = factor * legacy;
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
