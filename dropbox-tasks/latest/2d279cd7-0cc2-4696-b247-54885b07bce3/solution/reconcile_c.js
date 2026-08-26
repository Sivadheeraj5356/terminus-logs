// Opaque boundary condition resolver
function reconcile_c(buffers, mask, order) {
    const { curr, width, gridSize, ghost } = buffers;
    const N = gridSize;
    const W = width;
    const H = ghost; // which is 2
    
    const boundaries = mask.boundaries || {
        left: "dirichlet",
        right: "dirichlet",
        top: "dirichlet",
        bottom: "dirichlet"
    };

    // Naive Dirichlet boundary conditions on outer edges

    // 1. Apply to left and right boundaries (for all rows i including ghost rows)
    for (let i = 0; i < W; i++) {
        const row = i * W;
        // Left boundary
        if (boundaries.left === "dirichlet") {
            for (let d = 0; d < H; d++) {
                curr[row + d] = 0;
            }
        } else if (boundaries.left === "neumann") {
            for (let d = 1; d <= H; d++) {
                curr[row + H - d] = curr[row + H + d];
            }
        }
        
        // Right boundary
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

    // 2. Apply to top and bottom boundaries (for all columns j)
    for (let j = 0; j < W; j++) {
        // Top boundary
        if (boundaries.top === "dirichlet") {
            for (let d = 0; d < H; d++) {
                curr[d * W + j] = 0;
            }
        } else if (boundaries.top === "neumann") {
            for (let d = 1; d <= H; d++) {
                curr[(H - d) * W + j] = curr[(H + d) * W + j];
            }
        }
        
        // Bottom boundary
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
