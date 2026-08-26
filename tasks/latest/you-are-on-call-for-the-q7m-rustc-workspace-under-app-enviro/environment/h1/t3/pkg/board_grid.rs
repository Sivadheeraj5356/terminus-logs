#[path = "move_apply.rs"]
mod move_apply;
#[path = "op_b3.rs"]
mod op_b3;
#[path = "op_z2.rs"]
mod op_z2;

pub use move_apply::apply_uci;
pub use op_b3::op_b3;
pub use op_z2::op_z2;

pub type Sq = u8; // 0..63 a1=0

#[derive(Clone, Debug)]
pub struct GridView {
    pub cells: [u8; 64],
    pub side_white: bool,
}

#[derive(Clone, Copy, Debug, Default)]
pub struct Rights {
    pub k: bool,
    pub q: bool,
    pub kk: bool,
    pub qq: bool,
}

#[derive(Clone, Debug, Default)]
pub struct Snap {
    pub grid_hash: u64,
    pub rights_mask: u8,
    pub ep_sq: Option<Sq>,
    pub side_white: bool,
}

pub const START_FEN: &str = "startpos";

impl GridView {
    pub fn startpos() -> Self {
        let mut cells = [b' '; 64];
        let back = b"rnbqkbnr";
        for i in 0..8 {
            cells[i] = back[i].to_ascii_uppercase();
            cells[56 + i] = back[i];
        }
        for i in 0..8 {
            cells[8 + i] = b'P';
            cells[48 + i] = b'p';
        }
        Self {
            cells,
            side_white: true,
        }
    }

    pub fn placement_hash(&self) -> u64 {
        let mut h: u64 = 0xcbf29ce484222325;
        for c in self.cells {
            h ^= c as u64;
            h = h.wrapping_mul(0x100000001b3);
        }
        h
    }
}

impl Rights {
    pub fn mask(&self) -> u8 {
        let mut m = 0u8;
        if self.k {
            m |= 1;
        }
        if self.q {
            m |= 2;
        }
        if self.kk {
            m |= 4;
        }
        if self.qq {
            m |= 8;
        }
        m
    }

    pub fn from_mask(m: u8) -> Self {
        Self {
            k: m & 1 != 0,
            q: m & 2 != 0,
            kk: m & 4 != 0,
            qq: m & 8 != 0,
        }
    }
}
