use crate::k3::lane::Lane;

pub fn fnv1a32(input: &str) -> u32 {
    const OFFSET: u32 = 2166136261;
    const PRIME: u32 = 16777619;
    let mut hash = OFFSET;
    for byte in input.bytes() {
        hash ^= byte as u32;
        hash = hash.wrapping_mul(PRIME);
    }
    hash
}

pub fn fnv1a_8hex(input: &str) -> String {
    format!("{:08x}", fnv1a32(input))
}

pub fn chain_stamp(source_tail: &str, receiver_tail: &str, parent_pick: &str) -> String {
    fnv1a_8hex(&format!("{source_tail}|{receiver_tail}|{parent_pick}"))
}

pub fn rc_band(source_tail: &str, receiver_tail: &str, parent_pick: &str) -> u32 {
    if source_tail == receiver_tail {
        0
    } else {
        let stamp = fnv1a_8hex(&format!("{source_tail}|{receiver_tail}|{parent_pick}"));
        let slice = &stamp[0..4];
        let value = u32::from_str_radix(slice, 16).unwrap_or(0);
        (value % 900) + 100
    }
}

pub fn stream_tag(lane: &Lane) -> u32 {
    let mut tag = fnv1a32(&lane.lane_id);
    tag ^= lane.wrap_epoch;
    tag = tag.wrapping_mul(16777619);
    for link in &lane.source_chain {
        tag ^= fnv1a32(link);
        tag = tag.wrapping_mul(16777619);
    }
    tag ^= if lane.interrupted { 0xA5A5_5A5A } else { 0x5A5A_A5A5 };
    tag ^= if lane.retry_overwrite {
        0x0F0F_F0F0
    } else {
        0xF0F0_0F0F
    };
    tag
}

pub fn fold_digest_hex(stamps: &[String], journal_seq: u32, wrap_epoch: u32) -> String {
    let mut fold = journal_seq ^ wrap_epoch;
    for stamp in stamps {
        fold = fold.wrapping_add(u32::from_str_radix(stamp, 16).unwrap_or(0));
        fold = fold.rotate_left(5);
    }
    format!("{:08x}", fold)
}

pub fn encode_sidecar_blob(rows: &[crate::k3::report::ReportRow]) -> Vec<u8> {
    let mut out = Vec::with_capacity(rows.len() * 24);
    out.extend_from_slice(b"SWTB");
    out.extend_from_slice(&(rows.len() as u32).to_le_bytes());
    for row in rows {
        out.extend_from_slice(row.lane_id.as_bytes());
        out.push(0);
        out.extend_from_slice(&row.stream_tag.to_le_bytes());
        out.extend_from_slice(&row.rc_band.to_le_bytes());
        let stamp = u32::from_str_radix(&row.chain_stamp, 16).unwrap_or(0);
        out.extend_from_slice(&stamp.to_le_bytes());
    }
    out
}
