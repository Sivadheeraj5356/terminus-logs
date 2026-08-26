CXX=g++
CXXFLAGS=-Wall -Wextra -O2 -std=c++17 -Iinclude -Ilib -Isrc -Imesh
LDFLAGS=-lfftw3 -lm

LIB_OBJS=lib/ac_io.o lib/ac_json.o lib/ac_sha.o lib/ac_cfg.o lib/ac_filter.o lib/ac_grid.o \
	lib/op_a.o lib/reconcile_b.o lib/ac_lane_prepare.o mesh/stage_mesh.o
STAGE_OBJS=src/step_c.o src/emit_d.o src/ac_lane_finalize.o src/decoy_wrap_spectral.o

all: /app/bin/reso_sim

/app/bin/reso_sim: $(LIB_OBJS) $(STAGE_OBJS) src/reso_main.o
	mkdir -p /app/bin
	$(CXX) $(CXXFLAGS) -o /app/bin/reso_sim $(STAGE_OBJS) src/reso_main.o $(LIB_OBJS) $(LDFLAGS)

lib/%.o: lib/%.cpp
	$(CXX) $(CXXFLAGS) -c -o $@ $<

mesh/%.o: mesh/%.cpp
	$(CXX) $(CXXFLAGS) -c -o $@ $<

src/%.o: src/%.cpp
	$(CXX) $(CXXFLAGS) -c -o $@ $<

clean:
	rm -f $(LIB_OBJS) $(STAGE_OBJS) src/reso_main.o /app/bin/reso_sim

.PHONY: all clean
