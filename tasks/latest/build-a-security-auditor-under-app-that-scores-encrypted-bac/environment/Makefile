SHELL := /bin/bash

BIN_DIR := /app/bin
EBTA_BIN := $(BIN_DIR)/ebta
OUT_DIR := /app/verdicts
REPORT := $(OUT_DIR)/backup_trust_report.json

GO ?= go
GOFLAGS ?= -trimpath
LDFLAGS ?= -s -w

.PHONY: all build run clean tidy verify

all: build

build: $(BIN_DIR)
	$(GO) build $(GOFLAGS) -ldflags "$(LDFLAGS)" -o $(EBTA_BIN) ./bootstrap/ebta

run: build
	mkdir -p $(OUT_DIR)
	$(EBTA_BIN)

clean:
	rm -rf $(BIN_DIR)/ebta $(REPORT)

tidy:
	$(GO) mod tidy

verify:
	test -x $(EBTA_BIN)
	test -s $(REPORT)

$(BIN_DIR):
	mkdir -p $(BIN_DIR)
