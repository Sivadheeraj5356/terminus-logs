CARGO ?= cargo

.PHONY: all clean

APP_ROOT ?= /app

all:
	$(CARGO) build --release --locked
	mkdir -p $(APP_ROOT)/bin $(APP_ROOT)/output
	cp $(APP_ROOT)/target/release/pick-balance $(APP_ROOT)/bin/pick-balance

clean:
	$(CARGO) clean
