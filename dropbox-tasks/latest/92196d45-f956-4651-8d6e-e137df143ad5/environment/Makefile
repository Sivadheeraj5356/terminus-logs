CC := gcc
CFLAGS := -Wall -Wextra -O2 -Iinclude

OBJS := \
	rack_o/gen_merge.o \
	rack_o/merge_bias.o \
	weave_u/tie_fold.o \
	weave_u/carry_bias.o \
	weave_u/slot_weft.o \
	weave_u/coil_mesh.o \
	weave_u/cord_bias.o \
	loom_p/range_est.o \
	shard_k/bound_lane.o \
	shard_k/mix_idx.o \
	shard_k/lane_weft.o \
	shard_k/drum_mesh.o \
	shard_k/cord_lane.o \
	spool_q/cache_get.o \
	spool_q/epoch_slot.o \
	spool_q/gen_ring.o \
	spool_q/ring_weft.o \
	spool_q/loop_mesh.o \
	spool_q/cord_ring.o \
	vault_r/page_gate.o \
	vault_r/stamp_line.o \
	vault_r/mark_fold.o \
	vault_r/fold_weft.o \
	vault_r/phase_mesh.o \
	vault_r/cord_phase.o \
	reel_m/coil_bias.o \
	reel_m/drum_lane.o \
	prism_n/ray_slot.o \
	prism_n/phase_ring.o \
	opt/cost_model.o \
	opt/live_meter.o \
	engine/full_scan.o \
	engine/plan_drive.o \
	parser/key_fold.o \
	lib/digest_fold.o \
	decoy/heap_rank.o \
	extras/y_rank.o \
	bracket/exec_main.o

.PHONY: all clean

all: bin/plan_matrix

bin/plan_matrix: $(OBJS)
	mkdir -p bin
	$(CC) $(CFLAGS) -o bin/plan_matrix $(OBJS)

rack_o/gen_merge.o: rack_o/gen_merge.c include/plan_types.h
	$(CC) $(CFLAGS) -c -o $@ rack_o/gen_merge.c

rack_o/merge_bias.o: rack_o/merge_bias.c include/plan_types.h
	$(CC) $(CFLAGS) -c -o $@ rack_o/merge_bias.c

weave_u/tie_fold.o: weave_u/tie_fold.c include/plan_types.h
	$(CC) $(CFLAGS) -c -o $@ weave_u/tie_fold.c

weave_u/carry_bias.o: weave_u/carry_bias.c include/plan_types.h
	$(CC) $(CFLAGS) -c -o $@ weave_u/carry_bias.c

weave_u/slot_weft.o: weave_u/slot_weft.c include/plan_types.h
	$(CC) $(CFLAGS) -c -o $@ weave_u/slot_weft.c

weave_u/coil_mesh.o: weave_u/coil_mesh.c include/plan_types.h
	$(CC) $(CFLAGS) -c -o $@ weave_u/coil_mesh.c

weave_u/cord_bias.o: weave_u/cord_bias.c include/plan_types.h
	$(CC) $(CFLAGS) -c -o $@ weave_u/cord_bias.c

loom_p/range_est.o: loom_p/range_est.c include/plan_types.h
	$(CC) $(CFLAGS) -c -o $@ loom_p/range_est.c

shard_k/bound_lane.o: shard_k/bound_lane.c include/plan_types.h
	$(CC) $(CFLAGS) -c -o $@ shard_k/bound_lane.c

shard_k/mix_idx.o: shard_k/mix_idx.c include/plan_types.h
	$(CC) $(CFLAGS) -c -o $@ shard_k/mix_idx.c

shard_k/lane_weft.o: shard_k/lane_weft.c include/plan_types.h
	$(CC) $(CFLAGS) -c -o $@ shard_k/lane_weft.c

shard_k/drum_mesh.o: shard_k/drum_mesh.c include/plan_types.h
	$(CC) $(CFLAGS) -c -o $@ shard_k/drum_mesh.c

shard_k/cord_lane.o: shard_k/cord_lane.c include/plan_types.h
	$(CC) $(CFLAGS) -c -o $@ shard_k/cord_lane.c

spool_q/cache_get.o: spool_q/cache_get.c include/plan_types.h
	$(CC) $(CFLAGS) -c -o $@ spool_q/cache_get.c

spool_q/epoch_slot.o: spool_q/epoch_slot.c include/plan_types.h
	$(CC) $(CFLAGS) -c -o $@ spool_q/epoch_slot.c

spool_q/gen_ring.o: spool_q/gen_ring.c include/plan_types.h
	$(CC) $(CFLAGS) -c -o $@ spool_q/gen_ring.c

spool_q/ring_weft.o: spool_q/ring_weft.c include/plan_types.h
	$(CC) $(CFLAGS) -c -o $@ spool_q/ring_weft.c

spool_q/loop_mesh.o: spool_q/loop_mesh.c include/plan_types.h
	$(CC) $(CFLAGS) -c -o $@ spool_q/loop_mesh.c

spool_q/cord_ring.o: spool_q/cord_ring.c include/plan_types.h
	$(CC) $(CFLAGS) -c -o $@ spool_q/cord_ring.c

vault_r/page_gate.o: vault_r/page_gate.c include/plan_types.h
	$(CC) $(CFLAGS) -c -o $@ vault_r/page_gate.c

vault_r/stamp_line.o: vault_r/stamp_line.c include/plan_types.h
	$(CC) $(CFLAGS) -c -o $@ vault_r/stamp_line.c

vault_r/mark_fold.o: vault_r/mark_fold.c include/plan_types.h
	$(CC) $(CFLAGS) -c -o $@ vault_r/mark_fold.c

vault_r/fold_weft.o: vault_r/fold_weft.c include/plan_types.h
	$(CC) $(CFLAGS) -c -o $@ vault_r/fold_weft.c

vault_r/phase_mesh.o: vault_r/phase_mesh.c include/plan_types.h
	$(CC) $(CFLAGS) -c -o $@ vault_r/phase_mesh.c

vault_r/cord_phase.o: vault_r/cord_phase.c include/plan_types.h
	$(CC) $(CFLAGS) -c -o $@ vault_r/cord_phase.c

reel_m/coil_bias.o: reel_m/coil_bias.c include/plan_types.h
	$(CC) $(CFLAGS) -c -o $@ reel_m/coil_bias.c

reel_m/drum_lane.o: reel_m/drum_lane.c include/plan_types.h
	$(CC) $(CFLAGS) -c -o $@ reel_m/drum_lane.c

prism_n/ray_slot.o: prism_n/ray_slot.c include/plan_types.h
	$(CC) $(CFLAGS) -c -o $@ prism_n/ray_slot.c

prism_n/phase_ring.o: prism_n/phase_ring.c include/plan_types.h
	$(CC) $(CFLAGS) -c -o $@ prism_n/phase_ring.c

opt/cost_model.o: opt/cost_model.c include/plan_types.h
	$(CC) $(CFLAGS) -c -o $@ opt/cost_model.c

opt/live_meter.o: opt/live_meter.c include/plan_types.h
	$(CC) $(CFLAGS) -c -o $@ opt/live_meter.c

engine/full_scan.o: engine/full_scan.c include/plan_types.h
	$(CC) $(CFLAGS) -c -o $@ engine/full_scan.c

engine/plan_drive.o: engine/plan_drive.c include/plan_types.h
	$(CC) $(CFLAGS) -c -o $@ engine/plan_drive.c

parser/key_fold.o: parser/key_fold.c include/plan_types.h
	$(CC) $(CFLAGS) -c -o $@ parser/key_fold.c

lib/digest_fold.o: lib/digest_fold.c include/digest_fold.h include/plan_types.h
	$(CC) $(CFLAGS) -c -o $@ lib/digest_fold.c

decoy/heap_rank.o: decoy/heap_rank.c include/plan_types.h
	$(CC) $(CFLAGS) -c -o $@ decoy/heap_rank.c

extras/y_rank.o: extras/y_rank.c include/plan_types.h
	$(CC) $(CFLAGS) -c -o $@ extras/y_rank.c

bracket/exec_main.o: bracket/exec_main.c include/plan_types.h include/digest_fold.h
	$(CC) $(CFLAGS) -c -o $@ bracket/exec_main.c

clean:
	rm -f bin/plan_matrix $(OBJS)
