CC ?= gcc
CFLAGS ?= -std=c11 -Wall -Wextra -O2 -Iinclude
LDFLAGS ?=

SRCS := $(wildcard cfg/*.c tape/*.c fail/*.c acct/*.c bind/*.c canon/*.c lock/*.c internal/*.c audit/*.c util/*.c decoy/*.c main.c)
OBJS := $(SRCS:.c=.o)
BIN := bin/pam_audit

.PHONY: all clean
all: $(BIN)
$(BIN): $(OBJS)
	@mkdir -p bin
	$(CC) $(CFLAGS) -o $@ $(OBJS) $(LDFLAGS)
%.o: %.c
	$(CC) $(CFLAGS) -c -o $@ $<
clean:
	rm -rf bin
	find . -name '*.o' -delete
