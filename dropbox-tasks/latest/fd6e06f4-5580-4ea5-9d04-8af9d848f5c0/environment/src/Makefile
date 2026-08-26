CC = gcc
CFLAGS = -std=c11 -Wall -Wextra -O2 -I.
LDFLAGS = -lcurl

BIN = /app/bin/feature_lineage_verdict

all: $(BIN)

feature_audit.o: feature_audit.c feature_audit.h
	$(CC) $(CFLAGS) -c feature_audit.c -o feature_audit.o

feature_lineage_verdict.o: feature_lineage_verdict.c feature_audit.h
	$(CC) $(CFLAGS) -c feature_lineage_verdict.c -o feature_lineage_verdict.o

$(BIN): feature_audit.o feature_lineage_verdict.o
	mkdir -p /app/bin
	$(CC) $(CFLAGS) -o $(BIN) feature_audit.o feature_lineage_verdict.o $(LDFLAGS)

clean:
	rm -f feature_audit.o feature_lineage_verdict.o $(BIN)
