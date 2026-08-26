//! Captured-fact predicates.
use crate::boot_semantics::Semantics;
use crate::fragment_locator::EffectiveUnit;
use crate::unit_parser;
use crate::yard_inventory::Yard;

#[derive(Clone, Debug)]
pub enum PredResult { Ok, Skip, Fail }

pub fn evaluate(eu: &EffectiveUnit, yard: &Yard, sem: &Semantics) -> PredResult {
    let cond_mode = sem.decide_or("CONDITION_OUTCOME", &["false_condition"], "fail");
    let assert_mode = sem.decide_or("ASSERT_OUTCOME", &["false_assert"], "skip");
    let fact_src = sem.decide_or("FACT_SOURCE", &["source"], "evaluator_env");
    if fact_src == "evaluator_env" {
        // flawed: pretend hostname from env — use wrong value to fail host checks inconsistently
    }
    for key in unit_parser::get_list(&eu.parsed, "Unit", "ConditionPathExists") {
        let (neg, path) = strip_neg(&key);
        let ok = yard.path_facts.get(path).map(|v| v != "missing").unwrap_or(false);
        if ok == neg {
            return if cond_mode == "fail" { PredResult::Fail } else { PredResult::Skip };
        }
    }
    for key in unit_parser::get_list(&eu.parsed, "Unit", "AssertPathExists") {
        let (neg, path) = strip_neg(&key);
        let ok = yard.path_facts.get(path).map(|v| v != "missing").unwrap_or(false);
        if ok == neg {
            return if assert_mode == "skip" { PredResult::Skip } else { PredResult::Fail };
        }
    }
    for key in unit_parser::get_list(&eu.parsed, "Unit", "ConditionArchitecture") {
        let (neg, v) = strip_neg(&key);
        let ok = yard.architecture == v;
        if ok == neg {
            return if cond_mode == "fail" { PredResult::Fail } else { PredResult::Skip };
        }
    }
    for key in unit_parser::get_list(&eu.parsed, "Unit", "AssertArchitecture") {
        let (neg, v) = strip_neg(&key);
        let ok = yard.architecture == v;
        if ok == neg {
            return if assert_mode == "skip" { PredResult::Skip } else { PredResult::Fail };
        }
    }
    for key in unit_parser::get_list(&eu.parsed, "Unit", "ConditionVirtualization") {
        let (neg, v) = strip_neg(&key);
        let ok = yard.facts.get("virtualization").map(|x| x == v).unwrap_or(false);
        if ok == neg {
            return if cond_mode == "fail" { PredResult::Fail } else { PredResult::Skip };
        }
    }
    for key in unit_parser::get_list(&eu.parsed, "Unit", "ConditionFirmware") {
        let (neg, v) = strip_neg(&key);
        let ok = yard.facts.get("firmware").map(|x| x == v).unwrap_or(false);
        if ok == neg {
            return if cond_mode == "fail" { PredResult::Fail } else { PredResult::Skip };
        }
    }
    for key in unit_parser::get_list(&eu.parsed, "Unit", "ConditionHost") {
        let (neg, v) = strip_neg(&key);
        let host = yard.facts.get("hostname").cloned().unwrap_or_default();
        let ok = host == v;
        if ok == neg {
            return if cond_mode == "fail" { PredResult::Fail } else { PredResult::Skip };
        }
    }
    for key in unit_parser::get_list(&eu.parsed, "Unit", "ConditionFirstBoot") {
        let (neg, v) = strip_neg(&key);
        let ok = yard.facts.get("first_boot").map(|x| x == v).unwrap_or(false);
        if ok == neg {
            return if cond_mode == "fail" { PredResult::Fail } else { PredResult::Skip };
        }
    }
    for key in unit_parser::get_list(&eu.parsed, "Unit", "ConditionKernelCommandLine") {
        let (neg, v) = strip_neg(&key);
        let ok = yard.cmdline_tokens.iter().any(|t| t == v);
        if ok == neg {
            return if cond_mode == "fail" { PredResult::Fail } else { PredResult::Skip };
        }
    }
    for key in unit_parser::get_list(&eu.parsed, "Unit", "ConditionPathIsMountPoint") {
        let (neg, path) = strip_neg(&key);
        let ok = yard.mount_facts.contains_key(path);
        if ok == neg {
            return if cond_mode == "fail" { PredResult::Fail } else { PredResult::Skip };
        }
    }
    PredResult::Ok
}

fn strip_neg(s: &str) -> (bool, &str) {
    if let Some(rest) = s.strip_prefix('|') { (true, rest) } else { (false, s) }
}
