SHELL := /bin/bash

BIN_DIR := /app/bin
RESOLVER_BIN := $(BIN_DIR)/contact-resolver
OUT_DIR := /app/results
REPORT := $(OUT_DIR)/contact_stability_report.json

GO ?= go
GOFLAGS ?= -trimpath
LDFLAGS ?= -s -w

.PHONY: all build run clean tidy verify

all: build

build: $(BIN_DIR)
	$(GO) build $(GOFLAGS) -ldflags "$(LDFLAGS)" -o $(RESOLVER_BIN) ./replay

run: build
	mkdir -p $(OUT_DIR)
	$(RESOLVER_BIN)

clean:
	rm -rf $(BIN_DIR)/contact-resolver $(REPORT)

tidy:
	$(GO) mod tidy

verify:
	test -x $(RESOLVER_BIN)
	test -s $(REPORT)

$(BIN_DIR):
	mkdir -p $(BIN_DIR)
