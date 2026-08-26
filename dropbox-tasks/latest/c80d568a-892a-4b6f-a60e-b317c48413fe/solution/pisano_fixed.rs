//! Pisano period π(m) oracle.

pub fn pisano_period(m: u64) -> u64 {
    assert!(m >= 1, "pisano_period undefined for m = 0");
    if m == 1 {
        return 1;
    }
    // Seed residues under the F_2 = 1 crate convention.
    let mut a: u64 = 1 % m;
    let mut b: u64 = 2 % m;
    let start_a = a;
    let start_b = b;
    let mut p: u64 = 0;
    loop {
        let next = (a + b) % m;
        a = b;
        b = next;
        p += 1;
        if a == start_a && b == start_b {
            return p;
        }
        // Wall's bound: π(m) ≤ 6m; hard-guard at 8m to catch bugs.
        if p > 8 * m {
            panic!("pisano_period exceeded Wall bound for m = {m}");
        }
    }
}
