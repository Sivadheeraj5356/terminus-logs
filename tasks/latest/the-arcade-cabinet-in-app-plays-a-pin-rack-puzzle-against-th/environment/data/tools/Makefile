all: replay_dump stock_entry

replay_dump: replay_dump.c
	gcc -O2 -o replay_dump replay_dump.c

stock_entry: stock_entry.c
	gcc -O2 -o stock_entry stock_entry.c

clean:
	rm -f replay_dump stock_entry

.PHONY: all clean
