.PHONY: build run clean

BINARY := /app/build/qwavectl

build:
	@mkdir -p /app/build
	cd /app && go build -o build/qwavectl ./qwavectl/cmd/qwavectl

run: build
	/app/build/qwavectl

clean:
	rm -f /app/build/qwavectl /app/build/statevec_benchmark_report.json
