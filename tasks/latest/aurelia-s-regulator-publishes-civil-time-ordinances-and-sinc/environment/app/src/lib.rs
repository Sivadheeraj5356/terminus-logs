pub mod anchor;
pub mod api;
pub mod calendar;
pub mod cli;
pub mod config;
pub mod corpus;
pub mod db;
pub mod emit;
pub mod precedence;
pub mod timeline;

pub type Result<T> = std::result::Result<T, Box<dyn std::error::Error + Send + Sync>>;
