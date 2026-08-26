CXX := g++
CXXFLAGS := -std=c++17 -O2 -Wall -Wextra -Iinclude

tracecurve: src/main.cpp src/continuation.cpp include/continuation.hpp
	$(CXX) $(CXXFLAGS) src/main.cpp src/continuation.cpp -o tracecurve

clean:
	rm -f tracecurve
	rm -rf outputs
