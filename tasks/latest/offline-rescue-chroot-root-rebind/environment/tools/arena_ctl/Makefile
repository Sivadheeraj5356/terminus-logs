CC ?= gcc
CFLAGS ?= -Wall -Wextra -O2 -Isrc

all: arena_ctl

arena_ctl: src/main.o
	$(CC) $(CFLAGS) -o $@ src/main.o

src/%.o: src/%.c
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -f src/*.o arena_ctl
