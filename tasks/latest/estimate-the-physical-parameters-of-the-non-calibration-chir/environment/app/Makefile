CC ?= gcc
CFLAGS ?= -std=c11 -O2 -Wall -Wextra -Wpedantic -Iinclude
LDFLAGS ?= -lm -lsqlite3

SRC = src/main.c src/catalog.c src/obs.c src/output.c src/recover.c
OBJ = $(SRC:.c=.o)

.PHONY: all clean

all: bin/recover

bin/recover: $(OBJ)
	mkdir -p bin
	$(CC) $(CFLAGS) -o $@ $(OBJ) $(LDFLAGS)

clean:
	rm -rf bin $(OBJ)
