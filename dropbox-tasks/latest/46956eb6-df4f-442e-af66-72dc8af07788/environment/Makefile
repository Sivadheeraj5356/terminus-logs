CC = gcc
CFLAGS = -Wall -Wextra -O2 -g -Iinclude
LDFLAGS = -llmdb

SRCS = src/main.c src/tel_cli.c src/tel_db.c src/tel_keys.c src/tel_fd.c \
       src/tel_config.c src/tel_scan.c src/tel_correlate.c \
       src/tel_replay.c src/tel_journal.c src/tel_report.c src/tel_sha256.c src/tel_crc32c.c

OBJS = $(SRCS:.c=.o)

all: /app/bin/telreplay

/app/bin/telreplay: $(OBJS)
	mkdir -p /app/bin
	$(CC) $(CFLAGS) -o $@ $(OBJS) $(LDFLAGS)

clean:
	rm -f $(OBJS) /app/bin/telreplay

.PHONY: all clean
