REPORT ?= build/hardened-report.json
CONFIG ?= config/media.yaml
OPENAPI ?= openapi.yaml
PORT ?= 5055
YQ ?= $(shell command -v yq || true)

.PHONY: report clean run

report:
	mkdir -p build
	perl scripts/analyze.pl --yq "$(YQ)" --config "$(CONFIG)" --openapi "$(OPENAPI)" --port "$(PORT)" --report "$(REPORT)"

run:
	MEDIA_CONFIG=$(CONFIG) PORT=$(PORT) python api/app.py

clean:
	rm -rf build .tools
