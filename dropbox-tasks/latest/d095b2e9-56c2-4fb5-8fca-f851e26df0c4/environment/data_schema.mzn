int: n_residues;
int: n_rotamers;
int: n_states;
int: n_classes;
int: n_bridges;

set of int: RESIDUE = 1..n_residues;
set of int: ROTAMER = 1..n_rotamers;
set of int: STATE = 1..n_states;
set of int: CLASS = 1..n_classes;
set of int: BRIDGE = 1..n_bridges;

array[RESIDUE, ROTAMER] of 0..1: valid;
array[RESIDUE] of 1..n_rotamers: native_rotamer;
array[RESIDUE, ROTAMER] of 1..n_classes: aa_class;
array[RESIDUE, ROTAMER] of int: charge;
array[RESIDUE, ROTAMER] of int: exposure_penalty;
array[RESIDUE, ROTAMER] of int: mutation_penalty;
array[STATE, RESIDUE, ROTAMER] of int: unary_energy;
array[RESIDUE, RESIDUE] of 0..1: contact;
array[STATE, RESIDUE, ROTAMER, RESIDUE, ROTAMER] of int: pair_energy;
array[RESIDUE, ROTAMER, RESIDUE, ROTAMER] of 0..1: clash;

array[BRIDGE] of 1..n_residues: bridge_left;
array[BRIDGE] of 1..n_residues: bridge_right;
array[RESIDUE, ROTAMER] of 0..1: bridge_capable;
array[STATE, BRIDGE] of int: bridge_credit;

int: required_bridges;
int: mutation_budget;
int: charge_min;
int: charge_max;
array[CLASS] of int: class_min;
array[CLASS] of int: class_max;
int: target_state;
array[STATE] of int: stability_margin;

int: robust_weight;
int: mutation_weight;
int: exposure_weight;
