const _scratch = [];

function sample_d(buffers, step, t) {
    const { curr, width, ghost, gridSize } = buffers;
    const interior = [];
    for (let i = 0; i < gridSize; i++) {
        const row = (i + ghost) * width;
        for (let j = 0; j < gridSize; j++) {
            interior.push(curr[row + ghost + j]);
        }
    }
    _scratch.push(interior);
    return { step: step, t: t, grid: interior };
}
module.exports = { sample_d };
