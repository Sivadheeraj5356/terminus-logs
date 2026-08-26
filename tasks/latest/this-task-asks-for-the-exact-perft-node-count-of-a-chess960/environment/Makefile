CXX := g++
CXXFLAGS := -std=c++17 -O2 -Wall -Iinclude
SRC := src/board.cpp src/movegen.cpp src/io.cpp src/main.cpp
BIN := build/chess960_perft

$(BIN): $(SRC)
	mkdir -p build
	$(CXX) $(CXXFLAGS) -o $(BIN) $(SRC)

clean:
	rm -rf build
