CXX ?= g++
CXXFLAGS ?= -std=c++17 -O2 -g -Wall -Wextra -Iinclude
LDFLAGS ?=
LDLIBS ?=

LIB_SOURCES := $(wildcard src/*.cc) $(wildcard src/frame/*.cc) $(wildcard src/codec/*.cc) $(wildcard src/transport/*.cc) $(wildcard src/config/*.cc)
LIB_OBJECTS := $(LIB_SOURCES:.cc=.o)

CMD_SOURCES := $(wildcard cmd/framecore/*.cc)
CMD_OBJECTS := $(CMD_SOURCES:.cc=.o)

TARGET := framecore

EXAMPLE_SOURCES := $(wildcard examples/*.cc)
EXAMPLE_BINARIES := $(patsubst examples/%.cc,bin/%,$(EXAMPLE_SOURCES))

all: $(TARGET)

$(TARGET): $(LIB_OBJECTS) $(CMD_OBJECTS)
	$(CXX) $(LDFLAGS) -o $@ $^ $(LDLIBS)

%.o: %.cc
	$(CXX) $(CXXFLAGS) -c -o $@ $<

examples: $(EXAMPLE_BINARIES)

bin/%: examples/%.cc $(LIB_OBJECTS)
	@mkdir -p bin
	$(CXX) $(CXXFLAGS) $(LDFLAGS) -o $@ $< $(LIB_OBJECTS) $(LDLIBS)

clean:
	rm -f $(LIB_OBJECTS) $(CMD_OBJECTS) $(TARGET)
	rm -rf bin

.PHONY: all clean examples
