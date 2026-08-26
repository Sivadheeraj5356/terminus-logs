//! IPv4 CIDR parsing and containment. Frozen evidence.

use crate::ip::parse_ip;

pub struct Cidr {
    pub net: u32,
    pub prefix: u8,
}

pub fn parse_cidr(s: &str) -> Option<Cidr> {
    let (addr, prefix) = match s.split_once('/') {
        Some((a, p)) => {
            let pr: u8 = p.parse().ok()?;
            if pr > 32 {
                return None;
            }
            (a, pr)
        }
        None => (s, 32u8),
    };
    Some(Cidr {
        net: parse_ip(addr)?,
        prefix,
    })
}

impl Cidr {
    /// The network mask this block compares against, laid out octet by octet
    /// from the most significant end.
    fn mask(&self) -> u32 {
        let mut m: u32 = 0;
        let mut bits = self.prefix as u32;
        let mut shift: u32 = 24;
        while bits >= 8 {
            m |= 0xFF << shift;
            bits -= 8;
            if shift == 0 {
                break;
            }
            shift -= 8;
        }
        m
    }

    /// Containment test: `ip` is in the block iff it agrees with the network
    /// address across the mask.
    pub fn contains(&self, ip: u32) -> bool {
        let m = self.mask();
        (ip & m) == (self.net & m)
    }
}
