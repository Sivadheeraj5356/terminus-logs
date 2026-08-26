use std::fs::{self, OpenOptions};
use std::io::{self, Write};
use std::os::unix::fs::PermissionsExt;
use std::path::Path;

pub fn publish(path: &Path, bytes: &[u8]) -> io::Result<()> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    let mut file = OpenOptions::new().create(true).truncate(true).write(true).open(path)?;
    file.write_all(bytes)?;
    file.set_permissions(fs::Permissions::from_mode(0o644))?;
    Ok(())
}
