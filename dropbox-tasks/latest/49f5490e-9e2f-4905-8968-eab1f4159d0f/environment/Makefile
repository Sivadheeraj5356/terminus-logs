CXX ?= g++
CXXFLAGS ?= -std=c++20 -O0 -g0 -Wall -Wextra -Wpedantic -Werror -Iinclude
LDFLAGS ?= -lcrypto

COMMON_SOURCES := \
	src/io.cpp \
	src/types.cpp \
	src/control.cpp \
	src/policy_parser.cpp \
	src/policy_compiler.cpp \
	src/event.cpp \
	src/state_files.cpp \
	src/state_projection.cpp \
	src/modules.cpp \
	src/engine.cpp \
	src/ward.cpp \
	src/checkpoint.cpp \
	src/service.cpp \
	src/cli.cpp

COMMON_OBJECTS := $(COMMON_SOURCES:src/%.cpp=build/%.o)

.PHONY: all clean
all: bin/authctl bin/policyc

bin/authctl: $(COMMON_OBJECTS) build/authctl_main.o | bin
	$(CXX) $(CXXFLAGS) $^ -o $@ $(LDFLAGS)

bin/policyc: $(COMMON_OBJECTS) build/policyc_main.o | bin
	$(CXX) $(CXXFLAGS) $^ -o $@ $(LDFLAGS)

build/%.o: src/%.cpp
	@mkdir -p build
	$(CXX) $(CXXFLAGS) -c $< -o $@

bin:
	mkdir -p bin

clean:
	rm -rf build bin
