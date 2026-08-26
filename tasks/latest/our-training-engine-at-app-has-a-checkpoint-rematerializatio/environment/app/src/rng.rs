// Deterministic single-word PRNG. See engine_design.md sec. 6.
//
// Must expose: next_u64, uniform_open (0,1), below(n), normal (two draws),
// and state()/set_state() for snapshot/restore. The entire state is one u64;
// snapshot fidelity is what makes rematerialization and resume possible.
//
// TODO: implement.
