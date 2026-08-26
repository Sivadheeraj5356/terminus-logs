use std::fs;
use std::path::Path;

#[derive(Clone, Debug, Default)]
pub struct WalTail {
    pub records: Vec<String>,
}

impl WalTail {
    pub fn append(&mut self, line: &str) {
        self.records.push(line.to_string());
    }

    pub fn flush(&self, path: &Path) -> Result<(), String> {
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent).map_err(|e| e.to_string())?;
        }
        let body = self.records.join("\n");
        fs::write(path, body).map_err(|e| e.to_string())
    }
}
