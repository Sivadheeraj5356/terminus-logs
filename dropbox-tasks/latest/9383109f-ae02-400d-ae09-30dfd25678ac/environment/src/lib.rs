pub mod types;

#[path = "../proc"]
pub mod proc {
    pub mod ingest;
    pub mod tracker;
    pub mod ctrl;
    pub mod fmt_check;
    pub mod sorter;
}

#[path = "../data"]
pub mod data {
    pub mod meta_store;
}

#[path = "../infer"]
pub mod infer {
    pub mod predict;
    pub mod train;
}

#[path = "../check"]
pub mod check {
    pub mod validate;
    pub mod aggregate;
}
