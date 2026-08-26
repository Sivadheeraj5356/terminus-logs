use std::fs::File;
use std::io::{Read, Seek, SeekFrom};
use std::path::Path;

pub fn read_span(path: &Path, off: u64, len: usize) -> Result<Vec<u8>, String> {
    let mut f = File::open(path).map_err(|e| format!("open {}: {e}", path.display()))?;
    f.seek(SeekFrom::Start(off)).map_err(|e| format!("seek {}: {e}", path.display()))?;
    let mut buf = vec![0u8; len];
    f.read_exact(&mut buf).map_err(|e| format!("read {}: {e}", path.display()))?;
    Ok(buf)
}

pub fn read_all(path: &Path) -> Result<Vec<u8>, String> {
    std::fs::read(path).map_err(|e| format!("read {}: {e}", path.display()))
}
