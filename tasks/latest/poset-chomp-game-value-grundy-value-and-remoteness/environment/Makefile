CXX ?= g++
CXXFLAGS ?= -O2 -std=c++17
SRCS := $(wildcard src/*.cpp)

chomp: $(SRCS)
	$(CXX) $(CXXFLAGS) $(SRCS) -o chomp

clean:
	rm -f chomp
