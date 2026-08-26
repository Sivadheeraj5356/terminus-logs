.PHONY: build run clean

BIN := bin/marcrec

build:
	go build -o $(BIN) ./cmd/marcrec

run:
	$(BIN) --shelves /app/shelves --codex /app/codex --seals /app/seals --catalog /app/catalog --out /app/output/report.json

clean:
	rm -rf bin/marcrec /app/output/report.json
