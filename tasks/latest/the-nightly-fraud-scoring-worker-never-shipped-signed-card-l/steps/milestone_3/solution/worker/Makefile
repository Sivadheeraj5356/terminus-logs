CC = gcc
CFLAGS = -Wall -Wextra -O2 -std=c11
LDFLAGS = -lssl -lcrypto -lsqlite3 -lm -ldl

SRCS = main.c ledger.c hmac.c db.c features.c model.c
OBJS = $(SRCS:.c=.o)
TARGET = risk_worker

.PHONY: all clean

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)

%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -f $(OBJS) $(TARGET)
