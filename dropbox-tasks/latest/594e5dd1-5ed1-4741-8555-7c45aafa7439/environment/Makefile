CC ?= cc
BIN := bin/stringer

SOURCES := main.c

all: $(BIN)

$(BIN): $(SOURCES)
	@mkdir -p bin
	$(CC) -O2 -std=c11 -o $(BIN) main.c -lm

clean:
	rm -rf bin

.PHONY: all clean
