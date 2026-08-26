.PHONY: all clean
BIN=/opt/simbin

all:
	mkdir -p $(BIN)
	go build -o $(BIN)/balancectl ./cmd/balancectl

clean:
	rm -f $(BIN)/balancectl
