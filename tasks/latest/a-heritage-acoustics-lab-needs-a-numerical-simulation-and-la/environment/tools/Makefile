CXX=g++
CXXFLAGS=-Wall -Wextra -O2 -std=c++17 -I../include -I../lib -I../src
LDFLAGS=-lfftw3 -lm

all: gen_ct

gen_ct: gen_ct.cpp
	$(CXX) $(CXXFLAGS) -o gen_ct gen_ct.cpp $(LDFLAGS)

clean:
	rm -f gen_ct

.PHONY: all clean
