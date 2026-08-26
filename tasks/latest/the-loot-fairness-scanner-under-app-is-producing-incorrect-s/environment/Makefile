.PHONY: build run clean

BINARY := /app/out/lootfair

build:
	@mkdir -p /app/out
	cd /app && go build -o out/lootfair ./rollbench/lootfair

run: build
	/app/out/lootfair

clean:
	rm -f /app/out/lootfair /app/out/fairness_report.json
