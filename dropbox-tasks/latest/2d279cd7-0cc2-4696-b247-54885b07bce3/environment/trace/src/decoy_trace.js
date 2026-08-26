// Decoy trace helper — JSON stringify round-trip
function decoy_trace(buffers) {
    const { curr, width, ghost, gridSize } = buffers;
    const rows = [];
    for (let i = 0; i < gridSize; i++) {
        const row = [];
        for (let j = 0; j < gridSize; j++) {
            row.push(curr[(i + ghost) * width + ghost + j]);
        }
        rows.push(row);
    }
    return JSON.parse(JSON.stringify(rows));
}
module.exports = { decoy_trace };
