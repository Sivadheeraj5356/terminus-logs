CC ?= gcc
CFLAGS ?= -std=c11 -O0 -g -Wall -Wextra -Iinclude
LDFLAGS ?=
LDLIBS ?= -lefence

SOURCES := $(wildcard src/*.c) cmd/dyeworks/main.c
OBJECTS := $(SOURCES:.c=.o)
TARGET := dyeworks

all: $(TARGET)

$(TARGET): $(OBJECTS)
	$(CC) $(LDFLAGS) -o $@ $^ $(LDLIBS)

%.o: %.c
	$(CC) $(CFLAGS) -c -o $@ $<

clean:
	rm -f $(OBJECTS) $(TARGET)

.PHONY: all clean
