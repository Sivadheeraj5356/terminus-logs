// Opaque grid operation helper
function op_a(gridSize, dims) {
    const H = 2; // ghost width
    const W = gridSize + 2 * H;
    const size = W * W;
    
    // Naive nested array allocation (exceeds memory cap if recreated)
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
