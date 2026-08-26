CC = gcc
CFLAGS = -std=c11 -Wall -Wextra -O2 -I. -I/app/environment
LDFLAGS = -lcrypto

SRCS = \
	lib/digest.c \
	lib/pack.c \
	lib/scope.c \
	sig/seal/ticket_bind.c \
	sig/seal/stub_bind.c \
	sig/range/chain_link.c \
	sig/epoch/floor_epoch.c \
	kel/bcast/ledger_scan.c \
	kel/port/admit_k.c \
	kel/fold/trace_emit.c \
	kel/run/seal_stage.c \
	kel/run/policy_stage.c \
	kel/run/bcast_stage.c \
	kel/run/port_stage.c \
	kel/run/fold_stage.c \
	tools/depot/main.c

OBJS = $(SRCS:.c=.o)

.PHONY: all clean

all: tools/depot/depot bin/depot

tools/depot/depot: $(OBJS)
	@mkdir -p tools/depot
	$(CC) $(OBJS) -o $@ $(LDFLAGS)

bin/depot: tools/depot/depot
	@mkdir -p bin
	ln -sf ../tools/depot/depot $@

%.o: %.c
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -f $(OBJS) tools/depot/depot bin/depot
