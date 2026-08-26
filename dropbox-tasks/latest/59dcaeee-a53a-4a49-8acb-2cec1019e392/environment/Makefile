.PHONY: build run clean

build:
	go build -o /app/bin/rfimhyst ./cmd/fieldloop

run:
	go run ./cmd/fieldloop --model /app/environment/fixtures/model.json --field /app/environment/fixtures/field.tsv --output-dir /app/output

clean:
	rm -rf /app/output/trajectory.tsv /app/output/avalanches.jsonl /app/output/checkpoint.json
