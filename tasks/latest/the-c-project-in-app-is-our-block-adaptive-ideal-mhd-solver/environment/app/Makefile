CXX ?= g++
CXXFLAGS ?= -O2 -std=c++17

all: bin/amr_mhd

bin/amr_mhd: src/amr_mhd.cpp
	mkdir -p bin
	$(CXX) $(CXXFLAGS) -o bin/amr_mhd src/amr_mhd.cpp -lm

clean:
	rm -rf bin

.PHONY: all clean
