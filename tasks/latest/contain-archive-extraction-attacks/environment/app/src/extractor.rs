use std::ffi::OsString;
use std::fs::{self, File};
use std::io::{Read, Seek};
use std::path::{Path, PathBuf};

pub fn run(arguments: Vec<OsString>) -> Result<(), String> {
    if arguments.len() != 2 {
        return Err("usage: quarantine-extractor <archive> <destination>".into());
    }

    let input = PathBuf::from(&arguments[0]);
    let destination = PathBuf::from(&arguments[1]);
    fs::create_dir_all(&destination).map_err(|error| error.to_string())?;

    let mut file = File::open(&input).map_err(|error| error.to_string())?;
    let mut magic = [0_u8; 4];
    let count = file.read(&mut magic).map_err(|error| error.to_string())?;
    file.rewind().map_err(|error| error.to_string())?;

    if count == magic.len() && magic.starts_with(b"PK") {
        unpack_zip(file, &destination)
    } else {
        tar::Archive::new(file)
            .unpack(&destination)
            .map_err(|error| error.to_string())
    }
}

fn unpack_zip(file: File, destination: &Path) -> Result<(), String> {
    let mut archive = zip::ZipArchive::new(file).map_err(|error| error.to_string())?;
    for index in 0..archive.len() {
        let mut entry = archive.by_index(index).map_err(|error| error.to_string())?;
        let relative = entry
            .enclosed_name()
            .ok_or_else(|| "ZIP path left the destination".to_string())?;
        let output = destination.join(relative);

        if entry.is_dir() {
            fs::create_dir_all(&output).map_err(|error| error.to_string())?;
            continue;
        }

        if let Some(parent) = output.parent() {
            fs::create_dir_all(parent).map_err(|error| error.to_string())?;
        }
        let mut target = File::create(output).map_err(|error| error.to_string())?;
        std::io::copy(&mut entry, &mut target).map_err(|error| error.to_string())?;
    }
    Ok(())
}
