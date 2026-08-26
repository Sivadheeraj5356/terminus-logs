.PHONY: test build smoke clean

test:
	go test ./cmd/...

build:
	go build -o bin/drift-check ./cmd/beacon-drift

smoke:
	./scripts/smoke-test.sh

clean:
	rm -rf bin dist coverage.out
