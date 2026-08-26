# Latent stabilizer-burst coset physics

This contract defines an exact quantum-error-correction calculation for repeated planar stabilizer measurements. A physical history consists of one readout frame, a jointly selected collection of latent burst sources, and allowed Pauli-fault occurrences in each measured round. Stabilizer and logical signatures live in GF(2), while frame priors, burst priors, and fault energies are exact rational quantities. The complete finite history space must be resolved jointly: neither observation rounds nor burst sources are independent. JSON member order and whitespace are immaterial. Whenever a result is described as sorted, use ascending Unicode code-point order for identifiers.

## Experimental state space

The experiment is one JSON object with required members `schema`, `stabilizers`, `logical_observables`, `readout_frames`, `noise_families`, `pauli_mechanisms`, `burst_exposure_limit`, `burst_sources`, and `shots`. Unknown object members are ignored. `schema` is `stabilizer-burst-coset-inference/v2`. Every identifier is a nonempty string containing only ASCII letters, digits, `.`, `_`, or `-`; identifiers are case-sensitive and their namespaces are independent.

`stabilizers` contains 1 through 12 unique stabilizer IDs. `logical_observables` contains 1 through 4 unique logical IDs. Stabilizer order is nonphysical. Logical-observable order defines bit order in a joint logical-class key.

There are 1 through 4 readout frames. Each frame has:

- `id`: a unique frame ID;
- `prior_weight`: an exact rational weight;
- `detector_bias`: distinct listed stabilizer IDs;
- `forbidden_mechanisms`: distinct Pauli-mechanism IDs.
- `forbidden_bursts`: distinct burst-source IDs. A forbidden source cannot be selected with that frame.

There are 1 through 8 noise families. Each has a unique `id`, an integer `occurrence_limit` from 0 through 20, an integer `window_rounds` from 1 through 32, and an integer `window_limit` from 0 through 20. The occurrence limit applies to the total number of active occurrences in all shots and is inclusive. For each observed shot round `r`, the window limit inclusively caps occurrences in that family whose shot rounds `q` satisfy `0 <= r-q < window_rounds`. Windows end only at observed shot rounds; every active mechanism occurrence is counted once.

There are 1 through 18 Pauli mechanisms. Each has:

- `id`: a unique mechanism ID;
- `family_id`: a listed noise-family ID;
- `cycle`: an integer from 0 through 31;
- `coupler_id`: a nonempty identifier;
- `neg_log_weight`: an exact rational weight;
- `detection_events`: distinct listed stabilizer IDs toggled by the mechanism;
- `logical_operators`: distinct listed logical-observable IDs toggled by the mechanism.
- optional `delayed_detection_events`: a JSON object whose decimal keys are offsets from 1 through 31 and whose values are distinct listed stabilizer IDs. An omitted member is `{}`. An active occurrence at round `r` toggles the listed events in the observed shot at round `r+offset`, if such a shot exists;
- optional `recovery_rounds`: an integer from 0 through 31, defaulting to 0. After an occurrence at round `r`, its `(cycle, coupler_id)` cannot occur again at a later round `q` when `0 < q-r <= recovery_rounds`.

An exact rational weight is `N` or `N/D`, where `N` is a nonnegative decimal integer and `D` is a positive decimal integer. Leading zeroes and unreduced fractions are accepted. All arithmetic and comparisons are exact. A spectrum writes each weight as a reduced fraction with positive denominator, omitting `/1`.

### Latent burst sources

`burst_exposure_limit` is a nonnegative integer from 0 through 640. There are 0 through 10 `burst_sources`. A burst source is a single experiment-wide latent event, not a separate choice in every shot. Each source has:

- `id`: a unique burst-source ID;
- `family_id`: a listed noise-family ID. Selecting the source charges one occurrence to that family at `start_round`;
- `prior_weight`: an exact rational weight charged once when selected;
- `exclusive_group`: a nonempty identifier or null. At most one selected source may have a given non-null group;
- `start_round`: an integer from 0 through 31;
- `duration_rounds`: an integer from 1 through 32. The source is active at integer rounds from `start_round` through `start_round + duration_rounds - 1`, inclusively;
- `intensity`: an integer from 1 through 20;
- `blocked_coupler_ids`: distinct coupler IDs. While the source is active, no local Pauli occurrence using a listed coupler may be active;
- `detection_events_by_offset`: a JSON object whose decimal keys are distinct offsets from 0 through `duration_rounds - 1` and whose values are distinct listed stabilizer IDs;
- `logical_operators_by_offset`: the analogous object of distinct listed logical-observable IDs.

At an observed shot round `r`, a selected source uses offset `r - start_round`. When the offset is in the active interval, its listed detector and logical signatures toggle in that shot, its intensity contributes to the shot's burst load, and its coupler blocks apply even when no signature is listed at that offset. A source is still active during unobserved integer rounds. Its experiment-wide exposure is `intensity * duration_rounds`; the sum over selected sources must not exceed `burst_exposure_limit`, with equality allowed.

There are 1 through 5 shots, their IDs are unique, and the sum of all `candidate_mechanisms` lengths is at most 20. Each shot has:

- `id`: its shot ID;
- `round`: a unique integer from 0 through 31. Round order, not input array order or shot ID, defines temporal order;
- `measured_events`: distinct listed stabilizer IDs;
- `candidate_mechanisms`: distinct listed mechanism IDs; a candidate may be active at most once in this shot and is a separate occurrence in every other shot that lists it;
- `cycle_caps`: a JSON object whose decimal key for every cycle used by a candidate maps to an integer from 0 through 18. Additional keys representing cycles 0 through 31 are allowed.
- `burst_cap`: an integer from 0 through 200. The sum of intensities of all selected sources active at this shot's round cannot exceed it; equality is allowed.

## Physical Pauli-fault histories

For one readout frame and one shot at round `r`, XOR the frame's `detector_bias`, `detection_events` from every Pauli mechanism active in that shot, every delayed signature emitted by earlier active mechanisms that targets `r`, and every detector signature emitted at `r` by a selected burst source. The history is physical exactly when this equals `measured_events` at every observed round. All signatures combine by parity. A delayed or burst signature does not activate a local Pauli occurrence or add Pauli energy in the receiving shot.

No frame-forbidden mechanism or burst source may be selected. Selected burst sources must satisfy exclusive-group, total-exposure, per-shot burst-load, and active-interval coupler-block rules. Within one shot, no two active mechanisms may share both `cycle` and `coupler_id`. Across shots, the earlier occurrence's `recovery_rounds` controls reuse; the later mechanism's recovery value does not act retroactively. The number active in a cycle may not exceed that shot's `cycle_caps` value.

For family accounting, every active Pauli occurrence charges one occurrence at its shot round and every selected burst source charges one occurrence at its `start_round`. Both kinds of occurrence contribute to the same family `occurrence_limit`. At each observed shot round `r`, the sliding window counts all charged occurrences at rounds `q` satisfying `0 <= r-q < window_rounds`, including burst starts at unobserved rounds. The count cannot exceed `window_limit`. Detector events, delayed events, burst emissions, and logical operators are GF(2) sets: an identifier toggled an even number of times is absent. All feasibility rules apply simultaneously; none relaxes another.

For a complete physical history, each shot weight is the sum of its active Pauli-mechanism weights. Burst-source priors are charged once, not in every active round. Total weight is the frame prior plus all selected burst priors plus every shot weight. Peak-shot weight is the greatest Pauli shot weight; it excludes the frame and burst priors. Rank complete histories by:

1. smaller total weight;
2. smaller total burst exposure;
3. smaller peak-shot weight;
4. fewer selected burst sources;
5. fewer active Pauli-mechanism occurrences.

The `likelihood manifold` contains every complete physical history tied on all five quantities. Different frames, burst-source collections, or local Pauli collections are different histories even if their stabilizer and logical parities agree.

Sort shots by ascending `round`. XOR the local Pauli logical signature with every selected burst logical signature emitted at that shot. Encode the resulting parity as bits in input `logical_observables` order and write `<shot-id>:<bits>`; join shot components with `/`. This is the joint logical-class key. Count every manifold member once in frame support, burst support, and joint logical support. A manifold member contributes one to each selected source's burst-support count; unselected sources contribute zero for that member.

The representative key is `<frame-id>|bursts=<burst-list>|<shot-id>=<mechanism-list>|...`, using selected burst IDs and shot-local mechanism IDs in ascending ID order, with shots in ascending round order. Empty collections leave the text after `=` empty. The emitted history is the manifold member with the lexicographically smallest complete representative key.

## Resolved spectrum

A resolved spectrum has exactly `status`, `readout_frame`, `selected_bursts`, `shots`, `family_occupancy`, `likelihood_manifold`, and `representative_key`.

`status` is `resolved`. `readout_frame` has exactly `id`, normalized `prior_weight`, and sorted `detector_bias`.

`selected_bursts` contains the representative's selected sources sorted by ID. Each row has exactly `id`, `family_id`, normalized `prior_weight`, `exclusive_group`, integer `start_round`, integer inclusive `end_round`, integer `intensity`, integer `exposure`, and sorted `blocked_coupler_ids`. `end_round` is `start_round + duration_rounds - 1`; `exposure` is `intensity * duration_rounds`.

`shots` has one row per input shot, sorted by round. Each row has exactly:

- `id`, integer `round`, and sorted `measured_events`;
- sorted `burst_events`, the net GF(2) detector emission from selected burst sources at this round;
- sorted `inherited_events`, the net GF(2) set of delayed signatures arriving from all earlier active occurrences before local signatures are applied;
- sorted `active_mechanisms`;
- sorted `reproduced_events`, equal to `measured_events`;
- `burst_logical_coset`, the net burst-source logical parity in input logical-observable order with parity-zero IDs omitted;
- `logical_coset`, the combined local-Pauli and burst-source parity in input logical-observable order with parity-zero IDs omitted;
- integer `burst_load`, the sum of active selected-source intensities at this round;
- normalized `neg_log_weight`;
- `mechanisms_by_cycle`, with one row per occupied cycle sorted numerically. Each such row has integer `cycle` and sorted `mechanism_ids`. No active mechanisms means an empty array.

`family_occupancy` has one row per family sorted by family ID. Each row has exactly `family_id`, `pauli_occurrences`, `burst_occurrences`, `active_occurrences`, `occurrence_limit`, and `remaining_occurrences`. `active_occurrences` is the sum of the two kind-specific counts.

`likelihood_manifold` has exactly `total_neg_log_weight`, integer `burst_exposure`, `peak_shot_weight`, integer `burst_count`, integer `mechanism_count`, `multiplicity`, `frame_support`, `burst_support`, and `joint_logical_support`. Weights are normalized rationals. `multiplicity` counts the full manifold. `frame_support` has one row for every input frame, sorted by frame ID, including zero-count frames; each row has exactly `frame_id` and integer `count`. `burst_support` likewise has one row for every input burst source sorted by burst ID, with exactly `burst_id` and integer `count`. `joint_logical_support` contains only represented classes, sorted by `class_key`, with exactly `class_key` and integer `count`. Frame-support and joint-logical-support counts each sum to `multiplicity`; burst-support counts need not because one history may select several sources.

`representative_key` is the complete key of the emitted history.

## No physical history

If no readout frame admits a complete physical Pauli-fault history, write exactly these members:

```json
{"status":"no_physical_coset","frames_examined":0,"shots_examined":0}
```

The zeroes illustrate integer types. `frames_examined` is the number of input frames and `shots_examined` is the number of input shots. No other members are present.

## Reproducible laboratory handoff

Expose the inference calculation through `/workspace/infer_stabilizer_burst_cosets`. It receives exactly two positional paths: the observations and the coset-spectrum destination. Every other path count exits nonzero. A successful calculation honors both supplied locations, creates a missing destination parent directory, leaves the observation bytes unchanged, writes no standard output, and records exactly one result object. The calculation applies to every experiment within the bounded physical ensemble rather than assuming the public frame, burst-source, shot, or Pauli-mechanism identifiers.

The public measurement handoff is `/workspace/infer_stabilizer_burst_cosets /workspace/task_file/stabilizer-burst-observations.json /workspace/stabilizer-burst-coset-spectrum.json`.
