function reconcile_c(buffers, mask, order) {
    const { curr, width, gridSize, ghost } = buffers;
    const N = gridSize;
    const W = width;
    const H = ghost;
    const boundaries = mask.boundaries || {
        left: "dirichlet", right: "dirichlet", top: "dirichlet", bottom: "dirichlet"
    };
    for (let j = 0; j < W; j++) {
        if (boundaries.top === "dirichlet") {
            for (let d = 0; d < H; d++) curr[d * W + j] = 0;
        } else if (boundaries.top === "neumann") {
            for (let d = 1; d <= H; d++) curr[(H - d) * W + j] = curr[(H + d) * W + j];
        }
        if (boundaries.bottom === "dirichlet") {
            for (let d = 0; d < H; d++) curr[(H + N + d) * W + j] = 0;
        } else if (boundaries.bottom === "neumann") {
            for (let d = 1; d <= H; d++) curr[(H + N - 1 + d) * W + j] = curr[(H + N - 1 - d) * W + j];
        }
    }
    for (let i = 0; i < W; i++) {
        const row = i * W;
        if (boundaries.left === "dirichlet") {
            for (let d = 0; d < H; d++) curr[row + d] = 0;
        } else if (boundaries.left === "neumann") {
            for (let d = 1; d <= H; d++) curr[row + H - d] = curr[row + H];
        }
        if (boundaries.right === "dirichlet") {
            for (let d = 0; d < H; d++) curr[row + H + N + d] = 0;
        } else if (boundaries.right === "neumann") {
            for (let d = 1; d <= H; d++) curr[row + H + N - 1 + d] = curr[row + H + N - 1];
        }
    }
}
module.exports = { reconcile_c };
