SHELL := /bin/bash

BIN_DIR := /app/bin
CHECKER_BIN := $(BIN_DIR)/artifact-equivalence-checker
OUT_DIR := /app/output
REPORT := $(OUT_DIR)/equivalence_report.json

GO ?= go
GOFLAGS ?= -trimpath
LDFLAGS ?= -s -w

.PHONY: all build run clean tidy verify

all: build

build: $(BIN_DIR)
	$(GO) build $(GOFLAGS) -ldflags "$(LDFLAGS)" -o $(CHECKER_BIN) ./toolchain-cli

run: build
	mkdir -p $(OUT_DIR)
	$(CHECKER_BIN)

clean:
	rm -rf $(CHECKER_BIN) $(REPORT)

tidy:
	$(GO) mod tidy

verify:
	test -x $(CHECKER_BIN)
	test -s $(REPORT)

$(BIN_DIR):
	mkdir -p $(BIN_DIR)
