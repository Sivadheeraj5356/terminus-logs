//! Hand-rolled SHA-256 kept in the binary as a helper. Not on the algorithmic
//! surface — this module is deliberately excluded from source_digests.

#![allow(dead_code)]

const K: [u32; 64] = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
];

pub fn hex(data: &[u8]) -> String {
    let d = digest(data);
    let mut s = String::with_capacity(64);
    const HEX: &[u8; 16] = b"0123456789abcdef";
    for b in d.iter() {
        s.push(HEX[(*b >> 4) as usize] as char);
        s.push(HEX[(*b & 0x0f) as usize] as char);
    }
    s
}

pub fn digest(data: &[u8]) -> [u8; 32] {
    let mut st: [u32; 8] = [
        0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
        0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
    ];
    let bit_len = (data.len() as u64) * 8;
    let mut p = Vec::with_capacity(data.len() + 72);
    p.extend_from_slice(data);
    p.push(0x80);
    while p.len() % 64 != 56 { p.push(0); }
    p.extend_from_slice(&bit_len.to_be_bytes());
    for c in p.chunks_exact(64) { compress(&mut st, c); }
    let mut out = [0u8; 32];
    for (i, s) in st.iter().enumerate() {
        out[i*4..i*4+4].copy_from_slice(&s.to_be_bytes());
    }
    out
}

fn compress(st: &mut [u32; 8], b: &[u8]) {
    let mut w = [0u32; 64];
    for i in 0..16 {
        w[i] = ((b[i*4] as u32) << 24) | ((b[i*4+1] as u32) << 16) | ((b[i*4+2] as u32) << 8) | (b[i*4+3] as u32);
    }
    for i in 16..64 {
        let s0 = w[i-15].rotate_right(7) ^ w[i-15].rotate_right(18) ^ (w[i-15] >> 3);
        let s1 = w[i-2].rotate_right(17) ^ w[i-2].rotate_right(19) ^ (w[i-2] >> 10);
        w[i] = w[i-16].wrapping_add(s0).wrapping_add(w[i-7]).wrapping_add(s1);
    }
    let (mut a, mut b, mut c, mut d, mut e, mut f, mut g, mut h) =
        (st[0], st[1], st[2], st[3], st[4], st[5], st[6], st[7]);
    for i in 0..64 {
        let s1 = e.rotate_right(6) ^ e.rotate_right(11) ^ e.rotate_right(25);
        let ch = (e & f) ^ ((!e) & g);
        let t1 = h.wrapping_add(s1).wrapping_add(ch).wrapping_add(K[i]).wrapping_add(w[i]);
        let s0 = a.rotate_right(2) ^ a.rotate_right(13) ^ a.rotate_right(22);
        let mj = (a & b) ^ (a & c) ^ (b & c);
        let t2 = s0.wrapping_add(mj);
        h = g; g = f; f = e; e = d.wrapping_add(t1);
        d = c; c = b; b = a; a = t1.wrapping_add(t2);
    }
    st[0] = st[0].wrapping_add(a); st[1] = st[1].wrapping_add(b);
    st[2] = st[2].wrapping_add(c); st[3] = st[3].wrapping_add(d);
    st[4] = st[4].wrapping_add(e); st[5] = st[5].wrapping_add(f);
    st[6] = st[6].wrapping_add(g); st[7] = st[7].wrapping_add(h);
}
