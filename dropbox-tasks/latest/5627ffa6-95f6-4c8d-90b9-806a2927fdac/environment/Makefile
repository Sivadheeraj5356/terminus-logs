GO ?= go
BIN ?= /app/bin/plangen
export GOCACHE ?= /tmp/gocache
export GOFLAGS ?= -mod=mod
export GOPROXY ?= off
export CGO_ENABLED ?= 0

.PHONY: build rebuild clean

build:
	$(GO) build -trimpath -o $(BIN) ./cmd/plangen

rebuild:
	$(GO) build -a -trimpath -o $(BIN) ./cmd/plangen

clean:
	rm -f $(BIN)
