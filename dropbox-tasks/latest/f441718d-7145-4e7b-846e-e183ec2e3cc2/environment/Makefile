.PHONY: build test pipeline verify clean

export PATH := /usr/local/go/bin:$(PATH)
RUNTIME_BIN ?= /tmp/runtime
RUNTIME_ROOT ?= $(CURDIR)

build:
	go build -o $(RUNTIME_BIN) ./cmd/runtime

test:
	go test ./...

pipeline: build
	RUNTIME_ROOT=$(RUNTIME_ROOT) RUNTIME_BIN=$(RUNTIME_BIN) bash scripts/run_pipeline.sh

verify: pipeline
	RUNTIME_ROOT=$(RUNTIME_ROOT) RUNTIME_BIN=$(RUNTIME_BIN) bash scripts/verify.sh

clean:
	rm -rf state/* output/* cache/* || true
	mkdir -p state output cache state/checkpoints
