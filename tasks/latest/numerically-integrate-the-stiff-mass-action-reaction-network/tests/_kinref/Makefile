CXX ?= g++
CXXFLAGS ?= -O2 -std=c++17 -ffp-contract=off -fno-fast-math

all: kinref genassays

kinref: ref_main.cpp netfile.cpp policy.cpp network.cpp tableau.cpp
	$(CXX) $(CXXFLAGS) -o kinref ref_main.cpp netfile.cpp policy.cpp network.cpp tableau.cpp

genassays: gen_assays.cpp
	$(CXX) $(CXXFLAGS) -o genassays gen_assays.cpp

clean:
	rm -f kinref genassays

.PHONY: all clean
