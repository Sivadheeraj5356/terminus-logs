mod api;
mod audit;
mod auth;
mod authz;
mod config;
mod consensus;
mod crypto;
mod endorsement;
mod governance;
mod json;
mod middleware;
mod monitoring;
mod relayer;
mod server;
mod stake;
mod store;
mod types;
mod validator;

use audit::audit_log::AuditLog;
use config::policy::PolicyConfig;
use config::secrets::Secrets;
use std::sync::Arc;
use store::state::AppState;

fn main() {
    let mut config = PolicyConfig::default_config();
    if let Ok(path) = std::env::var("KEYSTONE_AUDIT_PATH") {
        config.audit_path = path;
    }
    let secrets = Secrets::load();
    let audit = AuditLog::new(&config.audit_path, secrets.clone());
    let state = Arc::new(AppState::new(config, secrets, audit));
    store::seed::seed(&state);

    let addr = std::env::var("KEYSTONE_ADDR").unwrap_or_else(|_| "127.0.0.1:8847".to_string());
    let threads = std::env::var("KEYSTONE_THREADS")
        .ok()
        .and_then(|v| v.parse::<usize>().ok())
        .unwrap_or(8);
    let app_state = Arc::clone(&state);
    server::serve(&addr, threads, move |request| {
        api::handle(&app_state, request)
    });
}
