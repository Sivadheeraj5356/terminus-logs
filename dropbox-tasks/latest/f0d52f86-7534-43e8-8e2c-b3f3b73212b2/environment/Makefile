CC ?= cc
CFLAGS ?= -std=gnu99 -O2 -Wall -Iinclude
LDLIBS ?= -lm

SRC := $(wildcard src/*.c)
OBJ := $(SRC:.c=.o)
HDR := $(wildcard include/*.h)

solver: $(OBJ)
	$(CC) $(CFLAGS) -o solver $(OBJ) $(LDLIBS)

src/%.o: src/%.c $(HDR)
	$(CC) $(CFLAGS) -c -o $@ $<

clean:
	rm -f solver src/*.o

.PHONY: clean
