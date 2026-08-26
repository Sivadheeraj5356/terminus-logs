CC := gcc
CFLAGS := -Wall -Wextra -O2 -Iinclude -lm

OBJS := 	phase_h/case_lane.o 	phase_h/restore_lane.o 	stencil_k/edge_table.o 	stencil_k/weld_fold.o 	crate_q/slab_pack.o 	crate_q/snap_fold.o 	ridge_o/decoy_lane.o 	lattice_p/decoy_fold.o 	lib/mesh_fold.o 	lib/fold_helpers.o 	decoy/vis_weld.o 	extras/y_mesh.o 	bracket/exec_main.o

.PHONY: all clean

all: bin/nav_matrix

bin/nav_matrix: $(OBJS)
	mkdir -p bin
	$(CC) $(CFLAGS) -o bin/nav_matrix $(OBJS)

phase_h/case_lane.o: phase_h/case_lane.c include/mesh_types.h
	$(CC) $(CFLAGS) -c -o $@ phase_h/case_lane.c

phase_h/restore_lane.o: phase_h/restore_lane.c include/mesh_types.h
	$(CC) $(CFLAGS) -c -o $@ phase_h/restore_lane.c

stencil_k/edge_table.o: stencil_k/edge_table.c include/mesh_types.h
	$(CC) $(CFLAGS) -c -o $@ stencil_k/edge_table.c

stencil_k/weld_fold.o: stencil_k/weld_fold.c include/mesh_types.h
	$(CC) $(CFLAGS) -c -o $@ stencil_k/weld_fold.c

crate_q/slab_pack.o: crate_q/slab_pack.c include/mesh_types.h
	$(CC) $(CFLAGS) -c -o $@ crate_q/slab_pack.c

crate_q/snap_fold.o: crate_q/snap_fold.c include/mesh_types.h
	$(CC) $(CFLAGS) -c -o $@ crate_q/snap_fold.c

ridge_o/decoy_lane.o: ridge_o/decoy_lane.c include/mesh_types.h
	$(CC) $(CFLAGS) -c -o $@ ridge_o/decoy_lane.c

lattice_p/decoy_fold.o: lattice_p/decoy_fold.c include/mesh_types.h
	$(CC) $(CFLAGS) -c -o $@ lattice_p/decoy_fold.c

lib/mesh_fold.o: lib/mesh_fold.c include/mesh_fold.h include/mesh_types.h include/harness_lane.h
	$(CC) $(CFLAGS) -c -o $@ lib/mesh_fold.c

lib/fold_helpers.o: lib/fold_helpers.c include/mesh_types.h
	$(CC) $(CFLAGS) -c -o $@ lib/fold_helpers.c

decoy/vis_weld.o: decoy/vis_weld.c include/mesh_types.h
	$(CC) $(CFLAGS) -c -o $@ decoy/vis_weld.c

extras/y_mesh.o: extras/y_mesh.c
	$(CC) $(CFLAGS) -c -o $@ extras/y_mesh.c

bracket/exec_main.o: bracket/exec_main.c include/mesh_types.h include/mesh_fold.h include/harness_lane.h
	$(CC) $(CFLAGS) -c -o $@ bracket/exec_main.c

clean:
	rm -f bin/nav_matrix $(OBJS)
