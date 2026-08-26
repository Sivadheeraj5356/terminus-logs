CC      ?= cc
CFLAGS  ?= -O2 -std=c11 -Wall -Wextra
SRC      = src/main.c src/wordio.c src/rules.c
BIN      = mangle

.PHONY: all test clean

all: $(BIN)

$(BIN): $(SRC) src/mangle.h src/rules.h
	$(CC) $(CFLAGS) -o $(BIN) $(SRC)

# In-repo unit tests for the rule engine. Builds a small harness against the
# engine translation unit and runs a handful of behavioural checks.
test: tests/unit.c src/wordio.c src/rules.c src/mangle.h src/rules.h
	$(CC) $(CFLAGS) -o tests/unit tests/unit.c src/wordio.c src/rules.c
	./tests/unit

clean:
	rm -f $(BIN) tests/unit
