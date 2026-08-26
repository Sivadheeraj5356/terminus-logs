.PHONY: build run clean

BIN := /app/bin/airbridge

build:
	mkdir -p /app/bin
	cd /app/jetway && go build -o $(BIN) .

run: build
	$(BIN)

clean:
	rm -rf /app/bin /app/output

.DEFAULT_GOAL := build
