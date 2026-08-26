.PHONY: assets build sidecar path-check

assets:
	python3 /app/environment/data/generate_ops_bundle.py
	python3 /app/environment/data/generate_inventory.py

build:
	@echo "embedserve hardening CLI uses interpreted PHP modules"

sidecar:
	test -f /app/environment/sidecar/tokenizer/Cargo.lock

path-check:
	bash /app/environment/ci/path_check.sh
