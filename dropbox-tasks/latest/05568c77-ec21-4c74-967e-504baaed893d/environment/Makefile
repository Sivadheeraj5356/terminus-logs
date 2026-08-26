.PHONY: build run clean

BINARY := /app/build/featrecon

build:
	@mkdir -p /app/build
	cd /app && go build -o build/featrecon ./featurectl

run: build
	/app/build/featrecon

clean:
	rm -f /app/build/featrecon /app/build/feature_resolution_report.json
