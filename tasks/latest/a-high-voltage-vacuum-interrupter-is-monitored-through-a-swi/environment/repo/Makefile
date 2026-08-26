CXX ?= g++
CXXFLAGS ?= -O2 -std=c++17 -Wall -Wextra -Wpedantic

arcguard: src/main.cpp
	$(CXX) $(CXXFLAGS) -o arcguard src/main.cpp

.PHONY: clean
clean:
	rm -f arcguard
