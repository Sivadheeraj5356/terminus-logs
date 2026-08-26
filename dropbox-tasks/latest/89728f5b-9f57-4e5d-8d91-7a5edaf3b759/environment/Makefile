.PHONY: build run clean

BINARY := /app/build/delegationintegrity

build:
	@mkdir -p /app/build
	cd /app && go build -o build/delegationintegrity ./cmd/delegationintegrity

run: build
	/app/build/delegationintegrity

clean:
	rm -f /app/build/delegationintegrity /app/build/delegation_integrity_snapshot.json
