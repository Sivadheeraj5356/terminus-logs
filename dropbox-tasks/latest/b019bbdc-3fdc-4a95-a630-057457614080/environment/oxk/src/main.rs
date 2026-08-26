use std::env;

fn main() {
    let mut args = env::args().skip(1);
    let verb = args.next().unwrap_or_default();
    match verb.as_str() {
        "knit" => {
            let prev: i32 = args.next().unwrap().parse().unwrap();
            let at_regen = args.next().unwrap() == "1";
            let free_s = args.next().unwrap_or_default();
            let free: Vec<i32> = if free_s.is_empty() {
                vec![]
            } else {
                free_s
                    .split(',')
                    .filter(|x| !x.is_empty())
                    .map(|x| x.parse().unwrap())
                    .collect()
            };
            match oxk::knit_u(prev, at_regen, &free) {
                Some(v) => println!("{v}"),
                None => println!("none"),
            }
        }
        "draw" => {
            let cool: f64 = args.next().unwrap().parse().unwrap();
            let channels: i32 = args.next().unwrap().parse().unwrap();
            let per_ch: f64 = args.next().unwrap().parse().unwrap();
            let cap: f64 = args.next().unwrap().parse().unwrap();
            let (used, ok) = oxk::draw_v(cool, channels, per_ch, cap);
            let flag = if ok { 1 } else { 0 };
            println!("{used:.10} {flag}");
        }
        _ => {
            eprintln!("usage: oxk-cli knit|draw ...");
            std::process::exit(2);
        }
    }
}
