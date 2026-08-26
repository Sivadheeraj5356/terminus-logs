# Tidevault model provenance

Tidevault uses a first-party, CPU-trained, quantized linear policy/value model. No checkpoint, engine, dataset, or Python dependency is downloaded during image build or play. The canonical checkpoint format is `tidevault-linear-v1`, stored with the `.tvnn` extension as one sorted compact ASCII JSON line containing explicit feature-name arrays, integer weights, training identity, and the shared dataset digest. Weight scale is 100,000.

The frozen value feature order is:

`bias`, `score_diff`, `ply`, `tides_completed`, `plies_to_tide`, `own_p1_left`, `own_p2_left`, `own_p3_left`, `opp_p1_left`, `opp_p2_left`, `opp_p3_left`, `empty_slots`, `own_board_weight`, `opp_board_weight`, `own_spoke_leads`, `opp_spoke_leads`, `tied_spokes`, `own_spoke_margin`, `own_max_spoke`, `opp_max_spoke`, `own_ring_i_weight`, `opp_ring_i_weight`, `own_ring_m_weight`, `opp_ring_m_weight`, `own_ring_o_weight`, `opp_ring_o_weight`.

The frozen policy feature order is:

`bias`, `power_1`, `power_2`, `power_3`, `power`, `placement_ring_i`, `placement_ring_m`, `placement_ring_o`, `rotation_ring_i`, `rotation_ring_m`, `rotation_ring_o`, `same_ring`, `direction_cw`, `direction_ccw`, `settled_sector`, `ply`, `plies_to_tide`, `score_diff`, `same_power_left`, `post_own_spoke_leads`, `post_opp_spoke_leads`, `post_tied_spokes`, `post_own_spoke_margin`, `immediate_own_points`, `immediate_opp_points`.

All features are integer and actor-relative. `settled_sector` is zero-based A through F. Current and post-action spoke margins sum own weight minus opposing weight across the six spokes. Immediate points are nonzero only when the candidate creates the half-full tide at ply 9 or the full-board tide at ply 18. Terminal values use the fixed win/loss sentinel plus the actor-relative cumulative-score margin.

## Training lineage

The current `core.py`, `model.py`, `search.py`, and `train.py` source SHA-256 values are respectively `fbcd39b53ad2289b1fbab5ae77405456d1723204af08574ba81d4f4102254eb9`, `a99477f4facfdee0d0f7b8bcbf55f8b84ae0082e6e8f4eaf242d7f28d5259746`, `ac8aff6b67db6217c7bd885555c5cfbaf4d379680d920a9bb84382139f44e6c8`, and `8bfeb92966461d5b3ef0cf27274a7a5c131529b5f6ae12c5f6ab6a63817fe10c`. Seed 20260720 produced 1,200 games, 21,600 samples, and dataset SHA-256 `68966f73c2edf89eca9a518eecca844c9c5d5ab308b584cf1c3a43a42db5d074`. The canonical training log SHA-256 is `5b23a0e585e046756693674793c129b220a96a00d2c69afd70e7c1974ab0281c`. A clean reproduction matched that log and every checkpoint byte-for-byte.

| Epoch | Model ID | SHA-256 |
| ---: | --- | --- |
| 1 | `tidevault-linear-s20260720-e0001` | `588cc9dd43cac20ebf622d3547f4e677e187d66cb4138be1dcea43090773931e` |
| 2 | `tidevault-linear-s20260720-e0002` | `9d6e9d4a7f937ef08c530a762bfaa9f2b7ccb50ddbf50a153cb4b0235627e431` |
| 4 | `tidevault-linear-s20260720-e0004` | `68920ae99a568aa74a85c1af3256c06b6590a95643792bcf00e11820dd519f0b` |
| 8 | `tidevault-linear-s20260720-e0008` | `d2f53ff0e0a7f02ea3a83cc21a4f184cad70253efb471a7f0552077c448b07e8` |
| 16 | `tidevault-linear-s20260720-e0016` | `73f57174c1b60a429d05c33b10a71a466b0746f12defb0c84a275e2a897e6575` |

Checkpoint screening used equal search controls and color-swapped games; epoch was never treated as a strength claim. The measured direct e1/e4 pair gave e1 one win and one draw. The release runtime therefore bundles e4 at `/opt/arena-private/mid.tvnn`, while the distinct strong reference bundles e1 at `/solution/strong.tvnn` with stronger measured search. `environment/difficulty_knobs.conf` attests the runtime model ID, checkpoint digest, corpus digest, and deterministic search tuple. `solution/solve.sh` separately attests the strong checkpoint.

The independent verifier parses canonical checkpoint bytes itself, reimplements every feature and search transition, and regenerates every recorded Violet action without importing runtime or solution rules. Training outputs are retained outside the release archive; the archive contains only the selected runtime and reference checkpoints.
