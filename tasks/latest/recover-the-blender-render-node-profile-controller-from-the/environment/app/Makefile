PY ?= python3
BIN = /usr/local/bin/blendprofile
UNIT = /etc/systemd/system/blendprofile-reconcile@.service
TMPFILES = /usr/lib/tmpfiles.d/blendprofile.conf

all:
	$(PY) -m py_compile src/blendprofile.py
	printf '%s\n' '#!/bin/sh' 'exec python3 /app/src/blendprofile.py "$$@"' > $(BIN)
	chmod 0755 $(BIN)
	install -D -m 0644 systemd/blendprofile-reconcile@.service $(UNIT)
	install -D -m 0644 tmpfiles.d/blendprofile.conf $(TMPFILES)

clean:
	rm -f $(BIN)
	rm -f $(UNIT) $(TMPFILES)
	rm -rf src/__pycache__

install: all

.PHONY: all clean install
