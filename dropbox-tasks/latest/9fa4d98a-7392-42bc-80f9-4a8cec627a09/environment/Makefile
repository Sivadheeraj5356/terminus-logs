RUSTC ?= rustc

lcgrecover: src/main.rs
	$(RUSTC) -O -o lcgrecover src/main.rs

.PHONY: clean
clean:
	rm -f lcgrecover
