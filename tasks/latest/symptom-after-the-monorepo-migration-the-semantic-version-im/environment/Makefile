.PHONY: build run clean

BINARY := /app/build/svis

build:
	@mkdir -p /app/build
	cd /app && go build -o build/svis ./impact-engine

run: build
	/app/build/svis

clean:
	rm -f /app/build/svis /app/build/impact_report.json
