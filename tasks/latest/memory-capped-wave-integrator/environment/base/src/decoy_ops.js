// Decoy grid operations
// This module provides alternative multidimensional array allocations
// used during early debugging and prototyping of smaller grids.

function createNestedGrid(gridSize) {
    const W = gridSize + 4;
    const H = gridSize + 4;
    const grid = new Array(W);
    for (let i = 0; i < W; i++) {
        grid[i] = new Array(H).fill(0.0);
    }
    return grid;
}

function freeNestedGrid(grid) {
    if (!grid) return;
    for (let i = 0; i < grid.length; i++) {
        grid[i] = null;
    }
}

module.exports = {
    createNestedGrid,
    freeNestedGrid
};
