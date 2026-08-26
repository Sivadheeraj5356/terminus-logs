pub fn run(args: &[String]) -> i32 {
    if args.len() < 2 {
        eprintln!("usage: rsx <compile|scan> ...");
        return 2;
    }
    match args[1].as_str() {
        "compile" => 1,
        "scan" => 1,
        _ => {
            eprintln!("unknown subcommand");
            2
        }
    }
}
