use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};

use crate::operation::{OpId, Operation};
use crate::replica::Replica;
use crate::sync::{apply_exports, collect_exports};
use crate::vector_clock::VectorClock;

pub fn replicate_pair(a: &mut Replica, b: &mut Replica) -> Result<usize, String> {
    let ab = sync_one(a, b)?;
    let ba = sync_one(b, a)?;
    Ok(ab + ba)
}

fn sync_one(target: &mut Replica, source: &Replica) -> Result<usize, String> {
    let mut transferred = 0usize;
    let mut pending: Vec<(Operation, VectorClock)> = source
        .export_log()
        .into_iter()
        .filter(|(op, _)| !target.has_op(&op.id()))
        .collect();
    pending.sort_by_key(|(op, _)| op.id());

    while !pending.is_empty() {
        pending.sort_by_key(|(op, _)| op.id());
        let mut remaining = Vec::new();
        let mut progress = false;
        for (op, clock) in pending {
            match target.apply_remote(op.clone(), clock.clone()) {
                Ok(()) => {
                    transferred += 1;
                    progress = true;
                }
                Err(_) => remaining.push((op, clock)),
            }
        }
        if !progress {
            return Err("failed to apply remote operations in dependency order".into());
        }
        pending = remaining;
    }

    let paths = target
        .dag()
        .diff_paths(source.dag())
        .map_err(|e| e.to_string())?;
    if paths.is_empty() {
        return Ok(transferred);
    }
    let exports = collect_exports(source.dag(), &paths).map_err(|e| e.to_string())?;
    apply_exports(target.dag_mut(), &exports).map_err(|e| e.to_string())?;
    transferred += exports.len();
    Ok(transferred)
}

pub fn insert_char(replica: &mut Replica, after: Option<OpId>, ch: char) -> Result<OpId, String> {
    let id = replica.next_id();
    let op = Operation::Insert { after, id, value: ch };
    replica.apply_local(op)?;
    Ok(id)
}

pub fn delete_id(replica: &mut Replica, id: OpId) -> Result<(), String> {
    let op = Operation::Delete { id };
    replica.apply_local(op)
}

pub struct StressReport {
    pub operations: u64,
    pub partitions: u32,
    pub converged: bool,
    pub left_text: String,
    pub right_text: String,
    pub left_root: [u8; 32],
    pub right_root: [u8; 32],
}

pub const PARTITION_STRESS_OPS: u32 = 2000;

pub fn run_partition_stress(seed: u64, operations: u32) -> Result<StressReport, String> {
    let mut rng = StdRng::seed_from_u64(seed);
    let mut left = Replica::new(1);
    let mut right = Replica::new(2);
    let mut partitioned = false;
    let mut partitions = 0u32;
    let mut head_left: Option<OpId> = None;
    let mut head_right: Option<OpId> = None;

    for step in 0..operations {
        if step > 0 && step % 137 == 0 {
            partitioned = !partitioned;
            if partitioned {
                partitions += 1;
            } else {
                replicate_pair(&mut left, &mut right)?;
            }
        }

        let target_left = rng.gen_bool(0.5);
        let ch = (b'a' + (step % 26) as u8) as char;
        if target_left {
            let after = head_left;
            let id = insert_char(&mut left, after, ch)?;
            head_left = Some(id);
            if !partitioned {
                let op = Operation::Insert {
                    after,
                    id,
                    value: ch,
                };
                let clock = left.clock().clone();
                right.apply_remote(op, clock)?;
                head_right = Some(id);
            }
        } else {
            let after = head_right;
            let id = insert_char(&mut right, after, ch)?;
            head_right = Some(id);
            if !partitioned {
                let op = Operation::Insert {
                    after,
                    id,
                    value: ch,
                };
                let clock = right.clock().clone();
                left.apply_remote(op, clock)?;
                head_left = Some(id);
            }
        }
    }

    replicate_pair(&mut left, &mut right)?;

    let left_text = left.materialize();
    let right_text = right.materialize();
    let converged = left_text == right_text && left.root_hash() == right.root_hash();

    Ok(StressReport {
        operations: operations as u64,
        partitions,
        converged,
        left_text,
        right_text,
        left_root: left.root_hash(),
        right_root: right.root_hash(),
    })
}

pub fn replay_identical_ops(seed: u64) -> Result<(Replica, Replica), String> {
    let _ = seed;
    let mut a = Replica::new(1);
    let mut b = Replica::new(2);
    let mut last: Option<OpId> = None;

    for idx in 0..4 {
        let ch = (b'w' + idx) as char;
        let id = a.next_id();
        let op = Operation::Insert {
            after: last,
            id,
            value: ch,
        };
        a.apply_local(op.clone())?;
        let clock = a.clock().clone();
        b.apply_remote(op, clock)?;
        last = Some(id);
    }

    Ok((a, b))
}
