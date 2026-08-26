.PHONY: all clean

BIN := vivostep
SRC := ./cmd/vivostep

all:
	CGO_ENABLED=0 go build -o $(BIN) $(SRC)

clean:
	rm -f $(BIN)

install:
	CGO_ENABLED=0 go build -o /usr/local/bin/$(BIN) $(SRC)
