CC = gcc
CFLAGS = -std=gnu11 -Wall -Wextra -O2 -Iinclude $(shell pkg-config --cflags libcurl jansson)
LDFLAGS = $(shell pkg-config --libs libcurl jansson) -lcrypto -lm

SRCS = src/main.c src/http.c src/markdown.c src/matrix.c src/assignment.c src/reconcile.c src/report.c
OBJS = $(SRCS:src/%.c=build/%.o)

.PHONY: all clean

all: bin/tofmass-bin
	@mkdir -p bin
	@printf '%s\n' '#!/bin/bash' 'exec /app/bin/tofmass-bin "$$@"' > bin/tofmass
	@chmod 0755 bin/tofmass

bin/tofmass-bin: $(OBJS)
	@mkdir -p bin
	$(CC) $(CFLAGS) -o $@ $(OBJS) $(LDFLAGS)

build/%.o: src/%.c
	@mkdir -p build
	$(CC) $(CFLAGS) -c -o $@ $<

clean:
	rm -rf build bin/tofmass-bin
