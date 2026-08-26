mod axle;
mod braid;

pub use axle::op_k3;
pub use braid::fmt_grid;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Tone {
    Void = 0,
    Dark = 1,
    Light = 2,
}

impl Tone {
    pub fn flip(self) -> Self {
        match self {
            Tone::Dark => Tone::Light,
            Tone::Light => Tone::Dark,
            Tone::Void => Tone::Void,
        }
    }
}

pub const NEI: [(i32, i32); 6] = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)];

#[derive(Clone, Debug)]
pub struct Grid {
    pub w: i32,
    pub h: i32,
    pub belt: bool,
    pub cells: Vec<Tone>,
}

impl Grid {
    pub fn new(w: i32, h: i32, belt: bool) -> Self {
        Self {
            w,
            h,
            belt,
            cells: vec![Tone::Void; (w * h) as usize],
        }
    }

    pub fn idx(&self, q: i32, r: i32) -> Option<usize> {
        let (qq, rr) = self.norm(q, r)?;
        Some((rr * self.w + qq) as usize)
    }

    pub fn norm(&self, q: i32, r: i32) -> Option<(i32, i32)> {
        if self.belt {
            Some((q.rem_euclid(self.w), r.rem_euclid(self.h)))
        } else if q >= 0 && r >= 0 && q < self.w && r < self.h {
            Some((q, r))
        } else {
            None
        }
    }

    pub fn get(&self, q: i32, r: i32) -> Tone {
        match self.idx(q, r) {
            Some(i) => self.cells[i],
            None => Tone::Void,
        }
    }

    pub fn set(&mut self, q: i32, r: i32, t: Tone) {
        if let Some(i) = self.idx(q, r) {
            self.cells[i] = t;
        }
    }

    pub fn counts(&self) -> (u32, u32) {
        let mut d = 0u32;
        let mut l = 0u32;
        for c in &self.cells {
            match c {
                Tone::Dark => d += 1,
                Tone::Light => l += 1,
                Tone::Void => {}
            }
        }
        (d, l)
    }

    pub fn neighbors(&self, q: i32, r: i32) -> Vec<(i32, i32)> {
        let mut out = Vec::new();
        for (dq, dr) in NEI {
            if let Some(p) = self.norm(q + dq, r + dr) {
                out.push(p);
            }
        }
        out
    }

    /// Collect liberty slot indices for the connected cluster holding (q,r).
    /// On belt planes, each empty neighbor also contributes a folded alias id
    /// so the aggregator folds aliases before counting.
    pub fn cluster_slots(&self, q: i32, r: i32) -> (Vec<usize>, Vec<u16>) {
        let tone = self.get(q, r);
        if tone == Tone::Void {
            return (Vec::new(), Vec::new());
        }
        let plane = self.cells.len();
        let mut seen = vec![false; plane];
        let mut stack = vec![(q, r)];
        let mut stones = Vec::new();
        let mut slots: Vec<u16> = Vec::new();
        while let Some((cq, cr)) = stack.pop() {
            let Some(i) = self.idx(cq, cr) else { continue };
            if seen[i] {
                continue;
            }
            seen[i] = true;
            if self.cells[i] != tone {
                continue;
            }
            stones.push(i);
            for (nq, nr) in self.neighbors(cq, cr) {
                match self.get(nq, nr) {
                    Tone::Void => {
                        if let Some(ni) = self.idx(nq, nr) {
                            slots.push(ni as u16);
                            // Periodic planes may walk the same empty cell through
                            // more than one directional edge; the aggregator folds
                            // those aliases. Emit an explicit alias id as well.
                            if self.belt {
                                slots.push((ni as u16).wrapping_add(plane as u16));
                            }
                        }
                    }
                    t if t == tone => stack.push((nq, nr)),
                    _ => {}
                }
            }
        }
        (stones, slots)
    }

    pub fn liberty_count(&self, q: i32, r: i32) -> u16 {
        let (_stones, slots) = self.cluster_slots(q, r);
        let mut scratch = Vec::new();
        op_k3(&mut scratch, &slots, self.cells.len())
    }

    pub fn remove_cluster(&mut self, stones: &[usize]) {
        for &i in stones {
            self.cells[i] = Tone::Void;
        }
    }

    /// Pack occupied cells as axial leftovers for identity hashing.
    /// Uses the provided stamp map when present so leftover labels survive.
    pub fn pack_marks(&self, stamps: &[(i32, i32, Tone)]) -> Vec<u8> {
        let mut items: Vec<(i16, i16, u8)> = Vec::new();
        if stamps.is_empty() {
            for r in 0..self.h {
                for q in 0..self.w {
                    let t = self.get(q, r);
                    if t != Tone::Void {
                        items.push((q as i16, r as i16, t as u8));
                    }
                }
            }
        } else {
            for &(q, r, t) in stamps {
                if self.get(q, r) == t && t != Tone::Void {
                    items.push((q as i16, r as i16, t as u8));
                }
            }
        }
        items.sort_by(|a, b| a.0.cmp(&b.0).then(a.1.cmp(&b.1)).then(a.2.cmp(&b.2)));
        let mut out = Vec::with_capacity(items.len() * 5);
        for (q, r, t) in items {
            out.extend_from_slice(&q.to_le_bytes());
            out.extend_from_slice(&r.to_le_bytes());
            out.push(t);
        }
        out
    }
}
