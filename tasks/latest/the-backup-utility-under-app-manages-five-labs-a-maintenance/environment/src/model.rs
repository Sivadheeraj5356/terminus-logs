#[derive(Debug, Clone)]
pub struct Part {
    pub id: String,
    pub len: usize,
    pub mark: String,
}

pub const STATUS_INDEXED: &str = "indexed";
pub const STATUS_SCANNED: &str = "scanned";
pub const STATUS_MERGED: &str = "merged";

#[derive(Debug, Clone)]
pub struct FilePlan {
    pub path: String,
    pub parts: Vec<Part>,
}

#[derive(Debug, Clone)]
pub struct Locator {
    pub object: String,
    pub offset: u64,
    pub len: usize,
}

#[derive(Debug, Clone)]
pub struct Hit {
    pub data: Vec<u8>,
    pub status: String,
    pub source: String,
}

#[derive(Debug, Clone)]
pub struct Row {
    pub repo: String,
    pub path: String,
    pub span: String,
    pub bytes: usize,
    pub status: String,
    pub source: String,
}
