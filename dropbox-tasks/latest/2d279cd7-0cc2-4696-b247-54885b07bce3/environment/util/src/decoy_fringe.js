// Decoy boundary conditions helper
// This module provides simple boundary operations for standard Dirichlet conditions.
// It is designed for testing flat boundaries without stencil order adjustments.

function applySimpleDirichlet(grid, width, height) {
    if (!grid) return;
    // Set all top/bottom boundary edges to zero
    for (let j = 0; j < width; j++) {
        grid[j] = 0.0;
        grid[(height - 1) * width + j] = 0.0;
    }
    // Set all left/right boundary edges to zero
    for (let i = 0; i < height; i++) {
        grid[i * width] = 0.0;
        grid[i * width + (width - 1)] = 0.0;
    }
}

module.exports = {
    applySimpleDirichlet
};
