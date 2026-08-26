//! Command-line front end over the bridge crate. Shipped inside the Node
//! package so it operates without any FFI runtime.
//!
//! Usage:
//!   vellum-cli identity
//!   vellum-cli digest '<json>'
//!   vellum-cli detached '<json>'

use std::process::exit;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let command = args.get(1).map(|s| s.as_str()).unwrap_or("");
    match command {
        "identity" => {
            println!("{}", vellum::identity_json());
        }
        "digest" => {
            let input = args.get(2).cloned().unwrap_or_default();
            match vellum::canonical_digest_str(&input) {
                Ok(hex) => println!("{hex}"),
                Err(e) => {
                    eprintln!("vellum-cli: {e}");
                    exit(1);
                }
            }
        }
        "detached" => {
            let input = args.get(2).cloned().unwrap_or_default();
            #[cfg(feature = "detached")]
            {
                match vellum::detached_digest_str(&input) {
                    Ok(Some(hex)) => println!("{hex}"),
                    Ok(None) => println!("null"),
                    Err(e) => {
                        eprintln!("vellum-cli: {e}");
                        exit(1);
                    }
                }
            }
            #[cfg(not(feature = "detached"))]
            {
                let _ = input;
                println!("null");
            }
        }
        _ => {
            eprintln!("vellum-cli: unknown command {command:?}");
            exit(2);
        }
    }
}
