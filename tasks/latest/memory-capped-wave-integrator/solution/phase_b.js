// Opaque interior stencil engine
function phase_b(buffers, dt, dx, order) {
    const { prev, curr, next, width, gridSize, ghost } = buffers;
    const c = 1.0;
    const c2 = c * c;
    const dt2 = dt * dt;
    const dx2 = dx * dx;
    
    const factor = c2 * dt2;
    
    // Naive nested array update assuming order 2
    if (order === 2) {
        const coeff = factor / dx2;
        for (let i = ghost; i < gridSize + ghost; i++) {
            const row = i * width;
            for (let j = ghost; j < gridSize + ghost; j++) {
                const idx = row + j;
                const laplacian = curr[idx + 1] + curr[idx - 1] + curr[idx + width] + curr[idx - width] - 4.0 * curr[idx];
                next[idx] = 2.0 * curr[idx] - prev[idx] + coeff * laplacian;
            }
        }
    } else if (order === 4) {
        const coeff = factor / (12.0 * dx2);
        for (let i = ghost; i < gridSize + ghost; i++) {
            const row = i * width;
            for (let j = ghost; j < gridSize + ghost; j++) {
                const idx = row + j;
                const laplacian = -curr[idx + 2] - curr[idx - 2] - curr[idx + 2 * width] - curr[idx - 2 * width]
                                  + 16.0 * (curr[idx + 1] + curr[idx - 1] + curr[idx + width] + curr[idx - width])
                                  - 60.0 * curr[idx];
                next[idx] = 2.0 * curr[idx] - prev[idx] + coeff * laplacian;
            }
        }
    } else {
        throw new Error("Unsupported stencil order: " + order);
    }
}
module.exports = { phase_b };
