GO ?= go
BINDIR = /app/bin
.PHONY: clean install test
clean:
	rm -rf $(BINDIR)
install:
	mkdir -p $(BINDIR)
	$(GO) build -trimpath -o $(BINDIR)/vault-qualify ./cmd/vault-qualify
	$(GO) build -trimpath -o $(BINDIR)/vault-inspect ./cmd/vault-inspect
	$(GO) build -trimpath -o $(BINDIR)/vault-legacy-check ./cmd/vault-legacy-check
test:
	$(GO) test ./...
