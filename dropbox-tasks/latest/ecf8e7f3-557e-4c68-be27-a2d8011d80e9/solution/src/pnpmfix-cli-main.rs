
use pnpmfix_core::{inspect, read_csv, report_to_json, Edge, PinRow, DepRow};
use std::collections::HashSet;
use std::env;
use std::process;

fn main() {
    let mut args: Vec<String> = env::args().skip(1).collect();
    if args.is_empty() { eprintln!("usage"); process::exit(2); }
    if args[0] == "--version" { println!("pnpmfix 0.8.6"); return; }
    if args[0] != "inspect" { eprintln!("unknown"); process::exit(2); }
    args.remove(0);
    let mut lane=String::new(); let mut edges_p=String::new(); let mut arts_p=String::new();
    let mut deps_p=String::new(); let mut mirrors_p=String::new(); let mut pins_p=String::new();
    let mut xor_p=String::new(); let mut bans_p=String::new(); let mut forb_p=String::new();
    let mut hops=0u32; let mut out=String::new();
    let mut i=0;
    while i < args.len() {
        let a=args[i].clone(); let v=args.get(i+1).cloned().unwrap_or_default();
        match a.as_str() {
            "--lane"=>lane=v, "--edges"=>edges_p=v, "--artifacts"=>arts_p=v, "--deps"=>deps_p=v,
            "--mirrors"=>mirrors_p=v, "--pins"=>pins_p=v, "--xor"=>xor_p=v, "--bans"=>bans_p=v,
            "--forbidden-hosts"=>forb_p=v, "--retention-hops"=>hops=v.parse().unwrap_or(0), "--out"=>out=v,
            _=>{eprintln!("unknown {a}"); process::exit(2);}
        }
        i+=2;
    }
    let edge_rows=filter_lane(&read_csv(&edges_p).expect("edges"), &lane);
    let edges: Vec<Edge>=edge_rows.iter().map(|r| Edge{parent:r[1].clone(), child:r[2].clone(), hard:r[3]=="hard"}).collect();
    let art_rows=filter_lane(&read_csv(&arts_p).expect("artifacts"), &lane);
    let artifacts: Vec<String>=art_rows.iter().map(|r| r[1].clone()).collect();
    let dep_rows=filter_lane(&read_csv(&deps_p).expect("deps"), &lane);
    let deps: Vec<DepRow>=dep_rows.iter().map(|r| DepRow{
        coordinate:r[1].clone(), provide:r[2].clone(), version:r[3].clone(),
        source_url:r[4].clone(), source_hash:r[5].clone(), patch_url:r[6].clone(),
    }).collect();
    let (_, mir_rows)=read_csv(&mirrors_p).expect("mirrors");
    let mirrors: HashSet<String>=mir_rows.into_iter().map(|r|r[0].clone()).collect();
    let (_, pin_rows)=read_csv(&pins_p).expect("pins");
    let pins: Vec<PinRow>=pin_rows.into_iter().map(|r| PinRow{dep:r[0].clone(), version:r[1].clone(), sha256:r[2].clone()}).collect();
    let xor_rows_f=filter_lane(&read_csv(&xor_p).expect("xor"), &lane);
    let xor_rows: Vec<(String,String)>=xor_rows_f.iter().map(|r|(r[1].clone(),r[2].clone())).collect();
    let (_, ban_rows)=read_csv(&bans_p).expect("bans");
    let bans: HashSet<String>=ban_rows.into_iter().map(|r|r[0].clone()).collect();
    let (_, forb_rows)=read_csv(&forb_p).expect("forbidden-hosts");
    let forbidden: Vec<String>=forb_rows.into_iter().map(|r|r[0].clone()).collect();
    let report=inspect(&lane, hops, &edges, &artifacts, &deps, &mirrors, &pins, &xor_rows, &bans, &forbidden);
    std::fs::write(&out, report_to_json(&report)+"\n").expect("write");
}
fn filter_lane(parsed:&(Vec<String>,Vec<Vec<String>>), lane:&str)->Vec<Vec<String>>{
    parsed.1.iter().filter(|r|r.first().map(|c|c.as_str())==Some(lane)).cloned().collect()
}
