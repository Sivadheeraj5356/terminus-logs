.PHONY: build run

build:
	go build -o bin/fleetd ./cmd/fleetd

run: build
	./scripts/start-fleetd.sh
