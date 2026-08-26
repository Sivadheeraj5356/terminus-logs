use crate::merkle::MerkleDag;
use crate::operation::{OpId, OpLog, Operation};
use crate::sequence::SequenceState;
use crate::vector_clock::VectorClock;

#[derive(Debug, Clone)]
pub struct Replica {
    id: u32,
    counter: u64,
    clock: VectorClock,
    sequence: SequenceState,
    dag: MerkleDag,
    log: OpLog,
}

impl Replica {
    pub fn new(id: u32) -> Self {
        Self {
            id,
            counter: 0,
            clock: VectorClock::new(),
            sequence: SequenceState::new(),
            dag: MerkleDag::new(id),
            log: OpLog::default(),
        }
    }

    pub fn id(&self) -> u32 {
        self.id
    }

    pub fn next_id(&mut self) -> OpId {
        self.counter += 1;
        OpId::new(self.id, self.counter)
    }

    pub fn clock(&self) -> &VectorClock {
        &self.clock
    }

    pub fn root_hash(&self) -> [u8; 32] {
        self.dag.root_hash()
    }

    pub fn materialize(&self) -> String {
        self.sequence.materialize()
    }

    pub fn visible_len(&self) -> usize {
        self.sequence.visible_len()
    }

    pub fn visible_op_ids(&self) -> Vec<OpId> {
        self.sequence.visible_op_ids()
    }

    pub fn op_count(&self) -> usize {
        self.log.len()
    }

    pub fn apply_local(&mut self, op: Operation) -> Result<(), String> {
        self.clock.increment(self.id);
        let snapshot = self.clock.clone();
        self.sequence
            .apply(&op)
            .map_err(|e| e.to_string())?;
        self.dag
            .ingest(&op, &snapshot)
            .map_err(|e| e.to_string())?;
        self.log.insert(op, snapshot);
        Ok(())
    }

    pub fn apply_remote(&mut self, op: Operation, remote_clock: VectorClock) -> Result<(), String> {
        self.clock.merge(&remote_clock);
        self.sequence
            .apply(&op)
            .map_err(|e| e.to_string())?;
        self.dag
            .ingest(&op, &remote_clock)
            .map_err(|e| e.to_string())?;
        self.log.insert(op, remote_clock);
        Ok(())
    }

    pub fn dag(&self) -> &MerkleDag {
        &self.dag
    }

    pub fn dag_mut(&mut self) -> &mut MerkleDag {
        &mut self.dag
    }

    pub fn export_log(&self) -> Vec<(Operation, VectorClock)> {
        self.log
            .sorted_ids()
            .into_iter()
            .filter_map(|id| self.log.get(&id).cloned())
            .collect()
    }

    pub fn has_op(&self, id: &OpId) -> bool {
        self.log.get(id).is_some()
    }
}
