.PHONY: build
build:
	cargo build --release --manifest-path /app/environment/Cargo.toml
	install -m 0755 target/release/relayctl /app/bin/relayctl
