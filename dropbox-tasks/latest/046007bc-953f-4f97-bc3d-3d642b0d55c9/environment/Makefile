CC ?= gcc
CFLAGS ?= -std=c11 -O0 -g -Wall -Wextra -Iinclude
LDLIBS ?= -lefence

SOURCES := $(wildcard src/*.c) cmd/imgscan/main.c
OBJECTS := $(SOURCES:.c=.o)
TARGET := imgscan

.PHONY: all clean
all: $(TARGET)

$(TARGET): $(OBJECTS)
	$(CC) $(CFLAGS) -o $@ $(OBJECTS) $(LDLIBS)

%.o: %.c
	$(CC) $(CFLAGS) -c -o $@ $<

clean:
	rm -f $(OBJECTS) $(TARGET)
