.PHONY: build unit demo clean

BIN_DIR := bin

build:
	@mkdir -p $(BIN_DIR)
	CGO_ENABLED=0 go build -o $(BIN_DIR)/proxy-local ./cmd/proxy-local
	CGO_ENABLED=0 go build -o $(BIN_DIR)/backend-capture ./cmd/backend-capture
	CGO_ENABLED=0 go build -o $(BIN_DIR)/spool-inspect ./cmd/spool-inspect

unit:
	go test ./...

demo: build
	./scripts/demo-current.sh

clean:
	rm -rf $(BIN_DIR)
	find state/spool -mindepth 1 -delete 2>/dev/null || true
