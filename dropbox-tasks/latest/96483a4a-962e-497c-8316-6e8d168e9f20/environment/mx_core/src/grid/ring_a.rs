/// Maps axial coordinates onto torus bounds.
pub fn ring_a(q: i32, r: i32, w: i32, h: i32) -> (i32, i32) {
    (q % w, r % h)
}
