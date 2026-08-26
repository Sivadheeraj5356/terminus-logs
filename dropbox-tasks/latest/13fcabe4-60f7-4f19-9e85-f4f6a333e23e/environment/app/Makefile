BIN := /app/bin/zonepub

.PHONY: build test clean vendor
build:
	@mkdir -p /app/bin
	go build -mod=vendor -o $(BIN) ./cmd/zonepub

vendor:
	go mod vendor

test:
	go test -mod=vendor ./...

clean:
	rm -rf /app/bin/zonepub vendor
