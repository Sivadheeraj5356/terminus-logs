CXX ?= g++
CXXFLAGS ?= -std=c++17 -O2 -Wall -Wextra -pedantic

SRC := $(wildcard src/*.cpp)
OBJ := $(SRC:.cpp=.o)
BIN := bin/mosaicctl

.PHONY: all clean

all: $(BIN)

$(BIN): $(OBJ)
	mkdir -p bin
	$(CXX) $(CXXFLAGS) -o $@ $(OBJ)

src/%.o: src/%.cpp src/types.hpp
	$(CXX) $(CXXFLAGS) -c -o $@ $<

clean:
	rm -f src/*.o $(BIN)
