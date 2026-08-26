CC := gcc
CFLAGS := -std=c11 -O2 -Wall -Wextra -pedantic -ffp-contract=off -Iinclude

erfsum: src/main.c src/erfsum.c include/erfsum.h
	$(CC) $(CFLAGS) src/main.c src/erfsum.c -o erfsum -lm

clean:
	rm -f erfsum
	rm -rf outputs
