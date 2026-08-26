.PHONY: build test run clean

build:
	go build -o bin/acl ./cmd/acl

test:
	go test ./...

run: build
	./bin/acl evaluate --rules testdata/rules_main.json --flows testdata/flows_main.ndjson

clean:
	rm -rf bin
