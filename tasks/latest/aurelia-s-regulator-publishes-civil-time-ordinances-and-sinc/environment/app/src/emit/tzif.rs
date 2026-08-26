use sha2::{Digest, Sha256};

use crate::timeline::{type_index, Zone};

const MAGIC: &[u8; 4] = b"TZif";

fn designations(zone: &Zone) -> (Vec<u8>, Vec<u8>) {
    let mut buf = Vec::new();
    let mut offs = Vec::new();
    for t in &zone.types {
        offs.push(buf.len() as u8);
        buf.extend_from_slice(t.abbrev.as_bytes());
        buf.push(0);
    }
    (buf, offs)
}

fn header(timecnt: u32, typecnt: u32, charcnt: u32) -> Vec<u8> {
    let mut out = Vec::with_capacity(44);
    out.extend_from_slice(MAGIC);
    out.push(0);
    out.extend_from_slice(&[0u8; 15]);
    for v in [typecnt, typecnt, 0, timecnt, typecnt, charcnt] {
        out.extend_from_slice(&v.to_be_bytes());
    }
    out
}

/// The offset table's consumers read version 1 zone files: a single block of 32-bit
/// transition times, and nothing after it.
pub fn serialize(zone: &Zone) -> Vec<u8> {
    let (chars, offs) = designations(zone);
    let typecnt = zone.types.len() as u32;
    let charcnt = chars.len() as u32;
    let index = type_index(zone);

    let mut out = header(zone.transitions.len() as u32, typecnt, charcnt);
    for tr in &zone.transitions {
        out.extend_from_slice(&(tr.ut as i32).to_be_bytes());
    }
    for tr in &zone.transitions {
        out.push(index[&(tr.utoff, tr.isdst, tr.abbrev.clone())]);
    }
    for (i, t) in zone.types.iter().enumerate() {
        out.extend_from_slice(&t.utoff.to_be_bytes());
        out.push(t.isdst);
        out.push(offs[i]);
    }
    out.extend_from_slice(&chars);
    for t in &zone.types {
        out.push(t.isstd);
    }
    for t in &zone.types {
        out.push(t.isut);
    }
    out
}

pub fn sha256_hex(data: &[u8]) -> String {
    let mut h = Sha256::new();
    h.update(data);
    h.finalize().iter().map(|b| format!("{b:02x}")).collect()
}
