RUSTC ?= rustc
BIN := bin/switcher

SOURCES := main.rs

all: $(BIN)

$(BIN): $(SOURCES)
	@mkdir -p bin
	$(RUSTC) -O -o $(BIN) main.rs

clean:
	rm -rf bin

.PHONY: all clean
