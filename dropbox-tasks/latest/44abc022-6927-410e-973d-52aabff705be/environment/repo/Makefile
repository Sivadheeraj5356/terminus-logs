CC ?= cc
CFLAGS ?= -O2 -std=c11 -Wall

all: lowess

lowess: lowess.c
	$(CC) $(CFLAGS) -o lowess lowess.c -lm

clean:
	rm -f lowess

.PHONY: all clean
