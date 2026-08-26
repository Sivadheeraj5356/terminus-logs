use std::fs;
use std::path::Path;

#[derive(Default)]
pub struct WalTail {
    lines: Vec<String>,
}

impl WalTail {
    pub fn append(&mut self, line: impl Into<String>) {
        self.lines.push(line.into());
    }

    pub fn flush(&self, path: &Path) -> Result<(), String> {
        let body = self.lines.join("\n");
        fs::write(path, body).map_err(|e| e.to_string())
    }
}
