mod grade_model;

use grade_model::{
    checkpoint_modes, continuous_modes, expected_report, pause_modes, ExpectedReport,
};
use std::env;
use std::fs;
use std::path::Path;
use std::process::Command;

const APP: &str = "/app";
const ENGINE: &str = "/app/build/demo_engine";
const DEFAULT_OUT: &str = "/app/output/recovery_report.json";
const MODE_COUNT: usize = 9;

#[derive(Clone, Debug)]
struct ObservedReport {
    scene_token: String,
    ledger_tail: u64,
    scalar_near: f64,
    addon_aux: f64,
    wrap_epoch: u32,
    refresh_stamp: u64,
    segment_generation: u32,
    journal_crc32: u32,
    raw: String,
}

fn fail(msg: &str) -> ! {
    eprintln!("verifier failure: {msg}");
    std::process::exit(1);
}

fn assert_true(cond: bool, msg: &str) {
    if !cond {
        fail(msg);
    }
}

fn finite_close(got: f64, want: f64) -> bool {
    if got.is_nan() || want.is_nan() {
        return false;
    }
    let tiny = 1e-13_f64;
    let denom = (got.abs() + want.abs() + 1.0) * tiny;
    let cutoff = if denom > tiny { denom } else { tiny };
    (got - want).abs() <= cutoff
}

fn run(cmd: &[&str]) -> Result<(), String> {
    let status = Command::new(cmd[0])
        .args(&cmd[1..])
        .status()
        .map_err(|e| format!("failed to launch {:?}: {e}", cmd))?;
    if status.success() {
        Ok(())
    } else {
        Err(format!("command failed: {:?} (status {status})", cmd))
    }
}

fn rebuild_release() -> Result<(), String> {
    let build = Path::new(APP).join("build");
    if build.exists() {
        fs::remove_dir_all(&build).map_err(|e| format!("failed to clear build dir: {e}"))?;
    }
    let env = format!("{APP}/environment");
    let build_s = build.to_string_lossy().to_string();
    run(&["cmake", "-S", &env, "-B", &build_s, "-DCMAKE_BUILD_TYPE=Release"])?;
    run(&["cmake", "--build", &build_s, "-j2"])
}

fn get_json_string(blob: &str, key: &str) -> Option<String> {
    let marker = format!("\"{key}\"");
    let pos = blob.find(&marker)?;
    let rest = &blob[pos + marker.len()..];
    let colon = rest.find(':')?;
    let value = rest[colon + 1..].trim_start();
    if !value.starts_with('"') {
        return None;
    }
    let tail = &value[1..];
    let end = tail.find('"')?;
    Some(tail[..end].to_string())
}

fn get_json_number(blob: &str, key: &str) -> Option<f64> {
    let marker = format!("\"{key}\"");
    let pos = blob.find(&marker)?;
    let rest = &blob[pos + marker.len()..];
    let colon = rest.find(':')?;
    let value = rest[colon + 1..].trim_start();
    let end = value
        .find(|c: char| {
            !(c.is_ascii_digit() || c == '.' || c == '-' || c == '+' || c == 'e' || c == 'E')
        })
        .unwrap_or(value.len());
    value[..end].parse::<f64>().ok()
}

fn parse_report(blob: &str) -> Result<ObservedReport, String> {
    Ok(ObservedReport {
        scene_token: get_json_string(blob, "scene_token").ok_or("missing scene_token")?,
        ledger_tail: get_json_number(blob, "ledger_tail")
            .ok_or("missing ledger_tail")?
            .round() as u64,
        scalar_near: get_json_number(blob, "scalar_near").ok_or("missing scalar_near")?,
        addon_aux: get_json_number(blob, "addon_aux").ok_or("missing addon_aux")?,
        wrap_epoch: get_json_number(blob, "wrap_epoch")
            .ok_or("missing wrap_epoch")?
            .round() as u32,
        refresh_stamp: get_json_number(blob, "refresh_stamp")
            .ok_or("missing refresh_stamp")?
            .round() as u64,
        segment_generation: get_json_number(blob, "segment_generation")
            .ok_or("missing segment_generation")?
            .round() as u32,
        journal_crc32: get_json_number(blob, "journal_crc32")
            .ok_or("missing journal_crc32")?
            .round() as u32,
        raw: blob.to_string(),
    })
}

fn emit(token: &str, out_path: &str) -> Result<ObservedReport, String> {
    if let Some(parent) = Path::new(out_path).parent() {
        fs::create_dir_all(parent).map_err(|e| format!("mkdir {out_path}: {e}"))?;
    }
    run(&[ENGINE, "emit", token, out_path])?;
    let blob = fs::read_to_string(out_path).map_err(|e| format!("read {out_path}: {e}"))?;
    parse_report(&blob)
}

fn compare_reports(obs: &ObservedReport, exp: &ExpectedReport, label: &str) {
    assert_true(
        obs.scene_token == exp.scene_token,
        &format!("{label}: scene_token got {}, want {}", obs.scene_token, exp.scene_token),
    );
    assert_true(
        obs.ledger_tail == exp.ledger_tail,
        &format!(
            "{label}: ledger_tail got {}, want {}",
            obs.ledger_tail, exp.ledger_tail
        ),
    );
    assert_true(
        finite_close(obs.scalar_near, exp.scalar_near),
        &format!(
            "{label}: scalar_near got {}, want {}",
            obs.scalar_near, exp.scalar_near
        ),
    );
    assert_true(
        finite_close(obs.addon_aux, exp.addon_aux),
        &format!(
            "{label}: addon_aux got {}, want {}",
            obs.addon_aux, exp.addon_aux
        ),
    );
    assert_true(
        obs.wrap_epoch == exp.wrap_epoch,
        &format!(
            "{label}: wrap_epoch got {}, want {}",
            obs.wrap_epoch, exp.wrap_epoch
        ),
    );
    assert_true(
        obs.refresh_stamp == exp.refresh_stamp,
        &format!(
            "{label}: refresh_stamp got {}, want {}",
            obs.refresh_stamp, exp.refresh_stamp
        ),
    );
    assert_true(
        obs.segment_generation == exp.segment_generation,
        &format!(
            "{label}: segment_generation got {}, want {}",
            obs.segment_generation, exp.segment_generation
        ),
    );
    assert_true(
        obs.journal_crc32 == exp.journal_crc32,
        &format!(
            "{label}: journal_crc32 got {}, want {}",
            obs.journal_crc32, exp.journal_crc32
        ),
    );
}

fn fnv_mix(mut h: u64, v: u64) -> u64 {
    h ^= v;
    h.wrapping_mul(1099511628211)
}

fn report_digest(rep: &ExpectedReport) -> u64 {
    let mut h = 14695981039346656037u64;
    for b in rep.scene_token.as_bytes() {
        h = fnv_mix(h, *b as u64);
    }
    h = fnv_mix(h, rep.ledger_tail);
    h = fnv_mix(h, rep.scalar_near.to_bits());
    h = fnv_mix(h, rep.addon_aux.to_bits());
    h = fnv_mix(h, rep.wrap_epoch as u64);
    h = fnv_mix(h, rep.refresh_stamp);
    h = fnv_mix(h, rep.segment_generation as u64);
    h = fnv_mix(h, rep.journal_crc32 as u64);
    h
}

fn matrix_digest(reports: &[ExpectedReport]) -> u64 {
    let mut h = 14695981039346656037u64;
    for rep in reports {
        h = fnv_mix(h, report_digest(rep));
    }
    h
}

fn reference_matrix() -> Vec<ExpectedReport> {
    (0..MODE_COUNT).map(expected_report).collect()
}

fn parse_trace_final_ledger(mode: usize) -> Result<u64, String> {
    let token = format!("Q{mode}");
    let output = Command::new(ENGINE)
        .args(["trace", &token])
        .output()
        .map_err(|e| format!("trace launch Q{mode}: {e}"))?;
    if !output.status.success() {
        return Err(format!("trace Q{mode} exited with {}", output.status));
    }
    let stderr = String::from_utf8_lossy(&output.stderr);
    let needle = "trace final ledger_tail=";
    let line = stderr
        .lines()
        .rev()
        .find(|l| l.contains(needle))
        .ok_or_else(|| format!("trace Q{mode} missing final ledger line"))?;
    let tail = line
        .split(needle)
        .nth(1)
        .ok_or_else(|| format!("trace Q{mode} malformed final ledger line"))?;
    let digits = tail
        .split_whitespace()
        .next()
        .ok_or_else(|| format!("trace Q{mode} missing ledger digits"))?;
    digits
        .parse::<u64>()
        .map_err(|e| format!("trace Q{mode} ledger parse: {e}"))
}

fn gate_enabled(name: &str) -> bool {
    match env::var("NLB_GATE") {
        Ok(filter) => {
            if filter.trim().is_empty() || filter == "all" {
                return true;
            }
            filter.split(',').any(|part| part.trim() == name)
        }
        Err(_) => true,
    }
}

fn test_scrambled_full_matrix() {
    let order = [8usize, 3, 0, 7, 1, 5, 2, 6, 4];
    for &mode in &order {
        let token = format!("Q{mode}");
        let exp = expected_report(mode);
        let out = format!("/tmp/nlb_scramble_{mode}.json");
        let obs = emit(&token, &out).unwrap_or_else(|e| fail(&format!("scrambled emit {token}: {e}")));
        compare_reports(&obs, &exp, &format!("scrambled_{mode}"));
    }
}

fn test_rebuild_after_every_token() {
    for mode in 0..MODE_COUNT {
        rebuild_release().unwrap_or_else(|e| fail(&format!("per-token rebuild {mode}: {e}")));
        let token = format!("Q{mode}");
        let exp = expected_report(mode);
        let out = format!("/tmp/nlb_rebuild_{mode}.json");
        let obs = emit(&token, &out).unwrap_or_else(|e| fail(&format!("post-rebuild emit {token}: {e}")));
        compare_reports(&obs, &exp, &format!("rebuild_isolated_{mode}"));
    }
}

fn test_composite_digest_lock() {
    let refs = reference_matrix();
    let want = matrix_digest(&refs);
    let mut obs_reports = Vec::with_capacity(MODE_COUNT);
    for mode in 0..MODE_COUNT {
        let token = format!("Q{mode}");
        let out = format!("/tmp/nlb_digest_{mode}.json");
        let obs = emit(&token, &out).unwrap_or_else(|e| fail(&format!("digest emit {token}: {e}")));
        compare_reports(&obs, &refs[mode], &format!("digest_row_{mode}"));
        obs_reports.push(ExpectedReport {
            scene_token: obs.scene_token,
            ledger_tail: obs.ledger_tail,
            scalar_near: obs.scalar_near,
            addon_aux: obs.addon_aux,
            wrap_epoch: obs.wrap_epoch,
            refresh_stamp: obs.refresh_stamp,
            segment_generation: obs.segment_generation,
            journal_crc32: obs.journal_crc32,
        });
    }
    let got = matrix_digest(&obs_reports);
    assert_true(
        got == want,
        &format!("composite digest got {got:#x}, want {want:#x}"),
    );
}

fn test_exact_ledger_pair_gaps() {
    let refs = reference_matrix();
    for mode in 0..MODE_COUNT {
        if mode == 0 {
            continue;
        }
        let gap = refs[mode - 1].ledger_tail - refs[mode].ledger_tail;
        assert_true(
            gap > 0,
            &format!("reference ledger gap Q{}-Q{} must be positive", mode - 1, mode),
        );
        let token_prev = format!("Q{}", mode - 1);
        let token_cur = format!("Q{mode}");
        let prev = emit(&token_prev, &format!("/tmp/nlb_gap_prev_{mode}.json"))
            .unwrap_or_else(|e| fail(&format!("gap emit {token_prev}: {e}")));
        let cur = emit(&token_cur, &format!("/tmp/nlb_gap_cur_{mode}.json"))
            .unwrap_or_else(|e| fail(&format!("gap emit {token_cur}: {e}")));
        let obs_gap = prev.ledger_tail - cur.ledger_tail;
        assert_true(
            obs_gap == gap,
            &format!(
                "ledger gap Q{}-Q{} got {}, want {}",
                mode - 1,
                mode,
                obs_gap,
                gap
            ),
        );
    }
}

fn test_trace_emit_agreement() {
    for mode in [5usize, 8, 1, 7] {
        let exp = expected_report(mode);
        let trace_ledger = parse_trace_final_ledger(mode)
            .unwrap_or_else(|e| fail(&format!("trace parse Q{mode}: {e}")));
        assert_true(
            trace_ledger == exp.ledger_tail,
            &format!(
                "trace vs reference ledger Q{mode}: trace {trace_ledger}, want {}",
                exp.ledger_tail
            ),
        );
        let out = format!("/tmp/nlb_trace_emit_{mode}.json");
        let obs = emit(&format!("Q{mode}"), &out)
            .unwrap_or_else(|e| fail(&format!("trace-emit Q{mode}: {e}")));
        assert_true(
            obs.ledger_tail == trace_ledger,
            &format!(
                "emit vs trace ledger Q{mode}: emit {}, trace {trace_ledger}",
                obs.ledger_tail
            ),
        );
        compare_reports(&obs, &exp, &format!("trace_emit_{mode}"));
    }
}

fn test_determinism_all_modes() {
    for mode in 0..MODE_COUNT {
        let token = format!("Q{mode}");
        let path_a = format!("/tmp/nlb_det_a_{mode}.json");
        let path_b = format!("/tmp/nlb_det_b_{mode}.json");
        let first = emit(&token, &path_a).unwrap_or_else(|e| fail(&format!("det first Q{mode}: {e}")));
        let second = emit(&token, &path_b).unwrap_or_else(|e| fail(&format!("det second Q{mode}: {e}")));
        assert_true(
            first.raw == second.raw,
            &format!("Q{mode} must emit byte-identical JSON on consecutive runs"),
        );
    }
}

fn test_addon_isolated_to_q5() {
    for mode in 0..MODE_COUNT {
        let exp = expected_report(mode);
        let token = format!("Q{mode}");
        let out = format!("/tmp/nlb_addon_{mode}.json");
        let obs = emit(&token, &out).unwrap_or_else(|e| fail(&format!("addon emit {token}: {e}")));
        if mode == 5 {
            assert_true(
                obs.addon_aux > 0.0,
                "Q5 addon_aux must be nonzero after post-resume churn",
            );
        } else {
            assert_true(
                finite_close(obs.addon_aux, 0.0),
                &format!("Q{mode} addon_aux must remain zero"),
            );
        }
        compare_reports(&obs, &exp, &format!("addon_gate_{mode}"));
    }
}

fn test_pause_vs_continuous_separation() {
    let q0 = expected_report(0);
    let q2 = expected_report(2);
    for mode in pause_modes() {
        let paused = expected_report(mode);
        assert_true(
            paused.ledger_tail != q0.ledger_tail && paused.ledger_tail != q2.ledger_tail,
            &format!("pause trial Q{mode} must not collapse to uninterrupted Q0/Q2 ledger"),
        );
        let token = format!("Q{mode}");
        let out = format!("/tmp/nlb_pause_{mode}.json");
        let obs = emit(&token, &out).unwrap_or_else(|e| fail(&format!("pause emit {token}: {e}")));
        compare_reports(&obs, &paused, &format!("pause_contract_{mode}"));
    }
    for mode in continuous_modes() {
        let exp = expected_report(mode);
        let token = format!("Q{mode}");
        let out = format!("/tmp/nlb_cont_{mode}.json");
        let obs = emit(&token, &out).unwrap_or_else(|e| fail(&format!("continuous emit {token}: {e}")));
        compare_reports(&obs, &exp, &format!("continuous_contract_{mode}"));
    }
}

fn test_alternate_output_paths() {
    for mode in [2usize, 5, 7, 8] {
        let token = format!("Q{mode}");
        let exp = expected_report(mode);
        let paths = [
            format!("/tmp/nlb_alt_a_{mode}.json"),
            format!("/tmp/nlb_alt_b_{mode}.json"),
            format!("/app/output/nlb_probe_{mode}.json"),
        ];
        let mut raws = Vec::new();
        for path in &paths {
            let obs = emit(&token, path).unwrap_or_else(|e| fail(&format!("alt path {path}: {e}")));
            compare_reports(&obs, &exp, &format!("alt_path_{mode}"));
            raws.push(obs.raw);
        }
        assert_true(
            raws.windows(2).all(|w| w[0] == w[1]),
            &format!("Q{mode} must be path-independent"),
        );
    }
}

fn test_scalar_band_invariants() {
    let refs = reference_matrix();
    let q0 = refs[0].scalar_near;
    let q4 = refs[4].scalar_near;
    let q5 = refs[5].scalar_near;
    assert_true(q4 > q0 + 1.0, "Q4 scalar_near must exceed Q0 band");
    assert_true(q5 > q4, "Q5 scalar_near must exceed Q4");
    for mode in 0..4 {
        let near = refs[mode].scalar_near;
        assert_true(
            (near - q0).abs() < 1.5,
            &format!("Q{mode} scalar_near must stay in the Q0-Q3 band"),
        );
        let token = format!("Q{mode}");
        let obs = emit(&token, &format!("/tmp/nlb_band_{mode}.json"))
            .unwrap_or_else(|e| fail(&format!("band emit {token}: {e}")));
        compare_reports(&obs, &refs[mode], &format!("band_contract_{mode}"));
    }
}

fn test_journal_thaw_replay_agreement() {
    for mode in [1usize, 5, 8] {
        let token = format!("Q{mode}");
        let snap = format!("/tmp/nlb_snap_{mode}.bin");
        let thaw_out = format!("/tmp/nlb_thaw_{mode}.json");
        let direct_out = format!("/tmp/nlb_direct_{mode}.json");
        run(&[ENGINE, "journal", "freeze", &token, &snap])
            .unwrap_or_else(|e| fail(&format!("journal freeze {token}: {e}")));
        run(&[ENGINE, "journal", "thaw", &token, &snap, &thaw_out])
            .unwrap_or_else(|e| fail(&format!("journal thaw {token}: {e}")));
        let thaw_blob = fs::read_to_string(&thaw_out)
            .unwrap_or_else(|e| fail(&format!("read thaw output {token}: {e}")));
        let thaw = parse_report(&thaw_blob)
            .unwrap_or_else(|e| fail(&format!("parse thaw output {token}: {e}")));
        let direct = emit(&token, &direct_out)
            .unwrap_or_else(|e| fail(&format!("direct emit {token}: {e}")));
        assert_true(
            thaw.raw == direct.raw,
            &format!("journal thaw Q{mode} must byte-match direct emit"),
        );
        compare_reports(&thaw, &expected_report(mode), &format!("journal_replay_{mode}"));
    }
}

fn test_segment_generation_checkpoint_only() {
    for mode in 0..MODE_COUNT {
        let exp = expected_report(mode);
        let token = format!("Q{mode}");
        let obs = emit(&token, &format!("/tmp/nlb_gen_{mode}.json"))
            .unwrap_or_else(|e| fail(&format!("gen emit {token}: {e}")));
        if checkpoint_modes().contains(&mode) {
            assert_true(
                obs.segment_generation == 1,
                &format!("checkpoint trial Q{mode} must report segment_generation=1"),
            );
        } else {
            assert_true(
                obs.segment_generation == 0,
                &format!("continuous trial Q{mode} must report segment_generation=0"),
            );
        }
        assert_true(
            obs.segment_generation == exp.segment_generation,
            &format!(
                "Q{mode} segment_generation got {}, want {}",
                obs.segment_generation, exp.segment_generation
            ),
        );
    }
}

fn test_journal_crc_partial_fix_trap() {
    for mode in [3usize, 6, 7] {
        let exp = expected_report(mode);
        let token = format!("Q{mode}");
        let obs = emit(&token, &format!("/tmp/nlb_crc_{mode}.json"))
            .unwrap_or_else(|e| fail(&format!("crc emit {token}: {e}")));
        assert_true(
            obs.journal_crc32 == exp.journal_crc32,
            &format!(
                "Q{mode} journal_crc32 got {}, want {} — ledger-only repairs fail here",
                obs.journal_crc32, exp.journal_crc32
            ),
        );
        assert_true(
            obs.wrap_epoch == exp.wrap_epoch,
            &format!(
                "Q{mode} wrap_epoch got {}, want {} — epoch fold must track restored crossings",
                obs.wrap_epoch, exp.wrap_epoch
            ),
        );
    }
}

fn test_refresh_stamp_exact_on_pause_trials() {
    for mode in [3usize, 6, 7] {
        let exp = expected_report(mode);
        let token = format!("Q{mode}");
        let obs = emit(&token, &format!("/tmp/nlb_stamp_{mode}.json"))
            .unwrap_or_else(|e| fail(&format!("stamp emit {token}: {e}")));
        compare_reports(&obs, &exp, &format!("stamp_contract_{mode}"));
    }
}

fn run_gate(name: &str, f: fn()) {
    if gate_enabled(name) {
        eprintln!("gate: {name}");
        f();
    }
}

fn main() {
    rebuild_release().unwrap_or_else(|e| fail(&format!("initial rebuild: {e}")));
    if !Path::new(ENGINE).is_file() {
        fail("release build must produce /app/build/demo_engine");
    }

    run_gate("scrambled_full_matrix", test_scrambled_full_matrix);
    run_gate("composite_digest_lock", test_composite_digest_lock);
    run_gate("exact_ledger_pair_gaps", test_exact_ledger_pair_gaps);
    run_gate("trace_emit_agreement", test_trace_emit_agreement);
    run_gate("rebuild_after_every_token", test_rebuild_after_every_token);
    run_gate("determinism_all_modes", test_determinism_all_modes);
    run_gate("addon_isolated_to_q5", test_addon_isolated_to_q5);
    run_gate("pause_vs_continuous_separation", test_pause_vs_continuous_separation);
    run_gate("alternate_output_paths", test_alternate_output_paths);
    run_gate("scalar_band_invariants", test_scalar_band_invariants);
    run_gate("journal_thaw_replay_agreement", test_journal_thaw_replay_agreement);
    run_gate("segment_generation_checkpoint_only", test_segment_generation_checkpoint_only);
    run_gate("journal_crc_partial_fix_trap", test_journal_crc_partial_fix_trap);
    run_gate("refresh_stamp_exact_on_pause_trials", test_refresh_stamp_exact_on_pause_trials);

    if gate_enabled("default_output_path") {
        let final_report = emit("Q0", DEFAULT_OUT)
            .unwrap_or_else(|e| fail(&format!("final default output: {e}")));
        compare_reports(&final_report, &expected_report(0), "default_output_path");
    }

    eprintln!("all neighbor-list-boundary verifier gates passed");
}
