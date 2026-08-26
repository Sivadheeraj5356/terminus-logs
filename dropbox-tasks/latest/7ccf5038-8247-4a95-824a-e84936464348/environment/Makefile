CC := gcc
CFLAGS := -std=c11 -O2 -Wall -Wextra -pedantic -ffp-contract=off -Iinclude

theta: src/main.c src/theta.c include/theta.h
	$(CC) $(CFLAGS) src/main.c src/theta.c -o theta -lm

clean:
	rm -f theta
	rm -rf outputs
