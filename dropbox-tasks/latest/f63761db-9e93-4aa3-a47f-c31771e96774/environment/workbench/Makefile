CXX ?= g++
CXXFLAGS ?= -std=c++20 -O2 -Wall -Wextra -Wpedantic -Werror
TARGET := /app/bin/kirigami-map
SOURCES := /app/workbench/main.cpp /app/workbench/model.cpp /app/workbench/solver.cpp

all: $(TARGET)

$(TARGET): $(SOURCES)
	$(CXX) $(CXXFLAGS) -I/app/workbench $(SOURCES) -o $(TARGET)

clean:
	rm -f $(TARGET)

.PHONY: all clean
