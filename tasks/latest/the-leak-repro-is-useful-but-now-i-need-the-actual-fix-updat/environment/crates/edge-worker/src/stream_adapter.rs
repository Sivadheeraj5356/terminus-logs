pub fn pack_bytes(input: &[u8]) -> Vec<u8> {
    let mut out = Vec::with_capacity(input.len());
    for chunk in input.chunks(3) {
        out.extend(chunk.iter().rev());
    }
    out
}
