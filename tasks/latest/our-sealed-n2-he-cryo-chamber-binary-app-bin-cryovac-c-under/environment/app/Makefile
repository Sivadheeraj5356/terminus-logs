CC = gcc
CFLAGS = -std=c11 -Wall -Wextra -O2 -Iinclude -D_DEFAULT_SOURCE
LDFLAGS = -lm

SRCS = src/main.c src/cli.c src/eos.c src/sorption.c src/condense.c src/calibrate.c src/chamber.c src/cJSON.c
OBJS = $(SRCS:.c=.o)
BIN = bin/cryovac

.PHONY: all clean

all: $(BIN)

$(BIN): $(OBJS)
	mkdir -p bin
	$(CC) $(CFLAGS) -o $@ $(OBJS) $(LDFLAGS)

src/%.o: src/%.c
	$(CC) $(CFLAGS) -c -o $@ $<

clean:
	rm -rf bin $(OBJS)
