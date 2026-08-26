use std::io::{self, Read, Write};

fn main() -> io::Result<()> {
    let mut input = Vec::new();
    io::stdin().read_to_end(&mut input)?;
    let packed = edge_worker::stream_adapter::pack_bytes(&input);
    io::stdout().write_all(&packed)?;
    Ok(())
}
