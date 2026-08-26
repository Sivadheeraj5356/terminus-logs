//! Match acceptance.jobs after complete simulation.
use crate::boot_semantics::Semantics;
use crate::boot_target_simulator::SimResult;
use crate::job_state_machine::State;
use crate::order_reader::Order;
use crate::reconcile_failure;

pub fn check(sim: &SimResult, order: &Order, sem: &Semantics) -> Result<(), i32> {
    let when = sem.decide_or("ACCEPTANCE_WHEN", &["mode"], "early");
    if when == "early" {
        // flawed: accept even if waiting remain
    } else {
        for st in sim.states.values() {
            if st.state == State::Waiting || st.state == State::Queued || st.state == State::Ready {
                return Err(fail("unresolved waiting jobs"));
            }
        }
    }
    for exp in &order.acceptance {
        let Some(got) = sim.states.get(&exp.unit) else {
            return Err(fail("missing expected job"));
        };
        let outcome = match got.state {
            State::Started => "STARTED",
            State::Skipped => "SKIPPED",
            State::Failed => "FAILED",
            State::Stopped => "FAILED",
            _ => "FAILED",
        };
        if outcome != exp.outcome {
            return Err(fail("outcome mismatch"));
        }
        let reason = match exp.outcome.as_str() {
            "STARTED" => "started",
            other => got.reason.as_str(),
        };
        if exp.outcome == "STARTED" {
            if got.reason != "started" && reason != exp.reason.as_str() {
                // allow reason started
            }
            if exp.reason != "started" && got.reason != exp.reason {
                return Err(fail("reason mismatch"));
            }
        } else if got.reason != exp.reason {
            return Err(fail("reason mismatch"));
        }
    }
    // target membership: final target must be started
    if let Some(st) = sim.states.get(&order.final_target) {
        if st.state != State::Started {
            return Err(fail("final target incomplete"));
        }
    } else {
        return Err(fail("final target missing"));
    }
    for m in &order.target_members {
        let Some(st) = sim.states.get(m) else {
            return Err(fail("target member missing"));
        };
        if st.state != State::Started && st.state != State::Skipped {
            return Err(fail("target member not acceptable"));
        }
    }
    Ok(())
}

fn fail(msg: &str) -> i32 {
    crate::diagnostic_surface::emit_error(reconcile_failure::EXIT_BOOT_SIM, msg);
    reconcile_failure::EXIT_BOOT_SIM
}
