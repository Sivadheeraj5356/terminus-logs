use ot7_core::handle;
use ot7_core::types::Request;
use std::io::{self, Read};

fn main() {
    let mut buf = String::new();
    io::stdin().read_to_string(&mut buf).unwrap();
    let req: Request = match serde_json::from_str(&buf) {
        Ok(r) => r,
        Err(e) => {
            println!("{{\"ok\":false,\"error\":\"parse: {}\",\"accepted\":false,\"plan\":[],\"wasserstein\":0.0,\"f\":[],\"g\":[],\"iters\":0}}", e);
            return;
        }
    };
    let resp = handle(req);
    println!("{}", serde_json::to_string(&resp).unwrap());
}
