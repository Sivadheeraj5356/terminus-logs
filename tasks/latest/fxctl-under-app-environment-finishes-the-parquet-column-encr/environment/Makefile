.PHONY: all clean

BIN := bin/fxctl
PEEK := bin/peek

all: $(BIN) $(PEEK)

$(BIN):
	mkdir -p bin
	go build -o $(BIN) ./cmd/fxctl

$(PEEK):
	mkdir -p bin
	go build -o $(PEEK) ./tools/peek

clean:
	rm -rf bin
