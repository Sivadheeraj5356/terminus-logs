CXX ?= g++
CXXFLAGS ?= -O2 -std=c++17 -ffp-contract=off -fno-fast-math

OBJS = bench_main.o policy.o network.o tableau.o systems.o

bench: $(OBJS)
	$(CXX) $(CXXFLAGS) -o bench $(OBJS)

%.o: %.cpp
	$(CXX) $(CXXFLAGS) -c -o $@ $<

clean:
	rm -f $(OBJS) bench

.PHONY: clean
