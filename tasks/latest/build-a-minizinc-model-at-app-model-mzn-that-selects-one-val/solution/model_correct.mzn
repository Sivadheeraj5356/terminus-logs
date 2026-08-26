include "/app/data_schema.mzn";

int: UB_STATE =
  sum(r in RESIDUE)(max([unary_energy[s,r,k] | s in STATE, k in ROTAMER])) +
  sum(r, q in RESIDUE where r < q)(
    max([pair_energy[s,r,k,q,l] | s in STATE, k, l in ROTAMER])
  );
int: UB_MUTATION = sum(r in RESIDUE)(max([mutation_penalty[r,k] | k in ROTAMER]));
int: UB_EXPOSURE = sum(r in RESIDUE)(max([exposure_penalty[r,k] | k in ROTAMER]));
int: UB_SECONDARY = n_states * UB_STATE + mutation_weight * UB_MUTATION + exposure_weight * UB_EXPOSURE;
int: UB_TOTAL = robust_weight * 2 * UB_STATE + UB_SECONDARY;

array[RESIDUE, ROTAMER] of var 0..1: select;
array[BRIDGE] of var 0..1: bridge;
array[CLASS] of var 0..n_residues: class_count;
array[STATE] of var 0..UB_STATE: state_energy;
var 0..n_residues: mutation_count;
var 0..UB_MUTATION: mutation_cost;
var 0..UB_EXPOSURE: exposure_cost;
var 0..(2 * UB_STATE): top_two_energy;
var 0..UB_SECONDARY: secondary_cost;
var 0..UB_TOTAL: total_cost;

array[RESIDUE, ROTAMER, RESIDUE, ROTAMER] of var 0..1: pair_choice;

constraint forall(r in RESIDUE)(
  sum(k in ROTAMER)(select[r,k]) = 1
);
constraint forall(r in RESIDUE, k in ROTAMER)(
  select[r,k] <= valid[r,k]
);

constraint forall(r, q in RESIDUE, k, l in ROTAMER where r < q)(
  pair_choice[r,k,q,l] <= select[r,k] /\
  pair_choice[r,k,q,l] <= select[q,l] /\
  pair_choice[r,k,q,l] >= select[r,k] + select[q,l] - 1
);
constraint forall(r, q in RESIDUE, k, l in ROTAMER where r >= q)(
  pair_choice[r,k,q,l] = 0
);
constraint forall(r, q in RESIDUE, k, l in ROTAMER where r < q)(
  pair_choice[r,k,q,l] <= 1 - clash[r,k,q,l]
);

constraint forall(c in CLASS)(
  class_count[c] = sum(r in RESIDUE, k in ROTAMER where aa_class[r,k] = c)(select[r,k]) /\
  class_count[c] >= class_min[c] /\
  class_count[c] <= class_max[c]
);
constraint sum(r in RESIDUE, k in ROTAMER)(charge[r,k] * select[r,k]) >= charge_min;
constraint sum(r in RESIDUE, k in ROTAMER)(charge[r,k] * select[r,k]) <= charge_max;

constraint mutation_count =
  sum(r in RESIDUE, k in ROTAMER where k != native_rotamer[r])(select[r,k]);
constraint mutation_count <= mutation_budget;
constraint mutation_cost =
  sum(r in RESIDUE, k in ROTAMER)(mutation_penalty[r,k] * select[r,k]);
constraint exposure_cost =
  sum(r in RESIDUE, k in ROTAMER)(exposure_penalty[r,k] * select[r,k]);

constraint sum(b in BRIDGE)(bridge[b]) = required_bridges;
constraint forall(b in BRIDGE)(
  bridge[b] <= sum(k in ROTAMER)(
    bridge_capable[bridge_left[b],k] * select[bridge_left[b],k]
  ) /\
  bridge[b] <= sum(k in ROTAMER)(
    bridge_capable[bridge_right[b],k] * select[bridge_right[b],k]
  )
);
constraint forall(r in RESIDUE)(
  sum(b in BRIDGE where bridge_left[b] = r \/ bridge_right[b] = r)(bridge[b]) <= 1
);

constraint forall(s in STATE)(
  state_energy[s] =
    sum(r in RESIDUE, k in ROTAMER)(unary_energy[s,r,k] * select[r,k]) +
    sum(r, q in RESIDUE, k, l in ROTAMER where r < q)(
      contact[r,q] * pair_energy[s,r,k,q,l] * pair_choice[r,k,q,l]
    ) -
    sum(b in BRIDGE)(bridge_credit[s,b] * bridge[b])
);
constraint forall(s in STATE where s != target_state)(
  state_energy[target_state] + stability_margin[s] <= state_energy[s]
);

constraint top_two_energy =
  max([state_energy[s1] + state_energy[s2] | s1, s2 in STATE where s1 < s2]);
constraint secondary_cost =
  sum(s in STATE)(state_energy[s]) +
  mutation_weight * mutation_cost +
  exposure_weight * exposure_cost;
constraint total_cost = robust_weight * top_two_energy + secondary_cost;

solve minimize total_cost;
