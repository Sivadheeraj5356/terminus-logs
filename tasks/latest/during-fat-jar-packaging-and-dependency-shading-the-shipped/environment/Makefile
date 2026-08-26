SHELL := /bin/bash

BIN_DIR := /app/bin
BIN := $(BIN_DIR)/reloccheck
OUT_DIR := /app/artifacts
REPORT := $(OUT_DIR)/relocation_consistency_report.json

GO ?= go
GOFLAGS ?= -trimpath
LDFLAGS ?= -s -w

.PHONY: all build run clean tidy verify

all: build

build: $(BIN_DIR)
	$(GO) build $(GOFLAGS) -ldflags "$(LDFLAGS)" -o $(BIN) ./relocbin

run: build
	mkdir -p $(OUT_DIR)
	$(BIN)

clean:
	rm -rf $(BIN) $(REPORT)

tidy:
	$(GO) mod tidy

verify:
	test -x $(BIN)
	test -s $(REPORT)

$(BIN_DIR):
	mkdir -p $(BIN_DIR)
