/// Display clamp used by board overlays; not part of sim stepping.
pub fn stub_wrap(q: i32, r: i32, w: i32, h: i32) -> (i32, i32) {
    let qq = if q < 0 {
        0
    } else if q >= w {
        w - 1
    } else {
        q
    };
    let rr = if r < 0 {
        0
    } else if r >= h {
        h - 1
    } else {
        r
    };
    (qq, rr)
}
