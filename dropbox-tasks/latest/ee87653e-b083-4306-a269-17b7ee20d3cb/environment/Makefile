CXX = g++
CXXFLAGS = -std=c++17 -Wall -Wextra -O2 -Iinclude

RELBIND_SRCS = core/main.cpp \
               elf/elf_helper.cpp \
               dynscan/encoding_probe.cpp \
               relmask/cipher_unmask.cpp \
               sectok/envelope_unpack.cpp \
               bindflow/witness_router.cpp

RELBIND_OBJS = $(RELBIND_SRCS:.cpp=.o)

.PHONY: all clean generate_binaries

all: bin/relbind bin/test_runner generate_binaries

bin/relbind: $(RELBIND_OBJS)
	@mkdir -p bin
	$(CXX) $(CXXFLAGS) -o $@ $^

bin/test_runner: test/test_runner.cpp
	@mkdir -p bin
	$(CXX) $(CXXFLAGS) -o $@ $^ -ldl

%.o: %.cpp
	$(CXX) $(CXXFLAGS) -c -o $@ $<

generate_binaries:
	@mkdir -p data/binaries
	python3 scripts/generate_test_binaries.py

clean:
	rm -rf bin/ $(RELBIND_OBJS) test/test_runner.o data/binaries/
