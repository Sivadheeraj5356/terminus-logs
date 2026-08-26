function op_a(gridSize, dims) {
    const H = 2;
    const W = gridSize + 2 * H;
    const size = W * W;

    if (!_slabPool.prev || _slabPool.size !== size) {
        _slabPool.prev = new Float64Array(size);
        _slabPool.curr = new Float64Array(size);
        _slabPool.next = new Float64Array(size);
        _slabPool.size = size;
    }

    return {
        prev: _slabPool.prev,
        curr: _slabPool.curr,
        next: _slabPool.next,
        width: W,
        height: W,
        gridSize: gridSize,
        ghost: H
    };
}
const _slabPool = { prev: null, curr: null, next: null, size: 0 };
module.exports = { op_a };
