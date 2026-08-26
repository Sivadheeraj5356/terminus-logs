/*
 * REDUCE_HOME (also restated in /app/environment/docs/pact_r8.md):
 * pack_fold(step, family, prev) = rotl64(prev,2) XOR ((step*149) XOR (family*23)) XOR rotr64(prev,7)
 * durable merge: if state.stamp >= stampB keep (u32)state.bits; else (u32)(state.bits XOR incoming.bits XOR (stampB<<1))
 * durable .seg: engine/seg_v/s<stamp>.seg is one line "<stamp> <bits:016x>"; empty s0.seg is incomplete
 * latch journal: after merge, write engine/seg_v/c7.jrnl as "lat <latch:08x> <stamp> <bits:016x>";
 *   persisted <stamp> equals the durable stamp loaded from .seg state (not incoming runtime progress);
 *   reload that line before emit; live latch alone is not bag/coherence authority
 * arm-combine ownership: u9p owns nest handshake combine; orch sequences stages and delegates
 * arm_combine(gateFirst, seed): run gate then side when true, else side then gate; each step is acc=(acc*K) XOR C
 *   side uses K=37 C=0x3131; gate uses K=19 C=0x4242
 * temporal arm chain: prev_pack starts 0; each arm packBits = arm_combine(gateFirst, local_fold XOR prev_pack);
 *   then prev_pack = packBits for the next arm (arm_tbl order)
 * emit_hx = lower16hex( fold64(arm_key) XOR packBits XOR latchVal XOR (held?0xC3C3:0) XOR witness.foldSeed XOR binSeed )
 * wit_hx = lower16hex( XOR of all emit_hx as u64 )
 * res_delta = ((packBits & 0xffff) / 65536.0) - base_v
 * mag = max abs(res_delta) across rows
 * band_lo=-1.0 band_hi=1.0 for fixture 49 attach residual policy
 * coherent iff replayed latch equals durable merge identity above
 * viol=0 iff every |res_delta|<=1.0 AND (coherent => bag_a==bag_b) AND (!coherent => bag_a!=bag_b)
 * lane_n = distinct lane_id count in hierarchy annex
 * held = 1.0 when arm_tbl held=true else 0.0
 * bag_a[i]=(packBits>>(i*8))&0xff; bag_b=bag_a when coherent else rotate-left-1
 * vec_core[i]=two lowercase hex chars of bag_a[i]
 * accept stamp: after emit write engine/seg_v/a2.stamp body = latch as 8 lowercase hex
 */

use std::env;
use std::path::PathBuf;

fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
    if args.is_empty() {
        eprintln!("usage: cg_xmit <run|gauge> ...");
        std::process::exit(2);
    }
    let cmd = args[0].as_str();
    if cmd == "gauge" {
        let mut envp = PathBuf::from("/app/environment");
        let mut i = 1usize;
        while i < args.len() {
            if args[i] == "--env" && i + 1 < args.len() {
                envp = PathBuf::from(&args[i + 1]);
                i += 2;
            } else {
                i += 1;
            }
        }
        println!("{}", engine::steady_label(&envp));
        return;
    }
    if cmd != "run" {
        eprintln!("unknown cmd");
        std::process::exit(2);
    }
    let mut pin: i32 = 49;
    let mut envp = PathBuf::from("/app/environment");
    let mut out = PathBuf::from("/app/output/protocol_transcript.json");
    let mut i = 1usize;
    while i < args.len() {
        match args[i].as_str() {
            "--pin" if i + 1 < args.len() => {
                pin = args[i + 1].parse().unwrap_or(49);
                i += 2;
            }
            "--env" if i + 1 < args.len() => {
                envp = PathBuf::from(&args[i + 1]);
                i += 2;
            }
            "--out" if i + 1 < args.len() => {
                out = PathBuf::from(&args[i + 1]);
                i += 2;
            }
            _ => i += 1,
        }
    }
    engine::run_pipeline(pin, &envp, &out);
}
