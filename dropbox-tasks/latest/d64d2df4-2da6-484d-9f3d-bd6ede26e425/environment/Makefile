.PHONY: all clean bins_d0 bins_stages bins_trace bins_probe tools

CC ?= gcc
CFLAGS ?= -Wall -Wextra -O2 -Ilib -Id0
LIB_SRCS = lib/parse_tok.c lib/epoch_chain.c lib/witness_gate.c

all: bins_d0 bins_stages bins_trace bins_probe tools

bins_d0:
	$(CC) $(CFLAGS) -o d0/j4_assemble d0/assemble.c $(LIB_SRCS) lib/sha256.c

bins_stages:
	$(CC) $(CFLAGS) -o d0/stg_u4 d0/stg_u4.c $(LIB_SRCS) lib/chain_seed.c
	$(CC) $(CFLAGS) -o d0/stg_m1 d0/stg_m1.c $(LIB_SRCS)
	$(CC) $(CFLAGS) -o d0/stg_p5 d0/stg_p5.c $(LIB_SRCS)
	$(CC) $(CFLAGS) -DTICK_APPLY_MAIN -o d0/tick_apply lib/tick_apply.c lib/epoch_chain.c lib/parse_tok.c
	$(CC) $(CFLAGS) -o d0/witness_refresh d0/witness_refresh.c lib/witness_gate.c lib/epoch_chain.c lib/parse_tok.c

bins_trace:
	$(CC) $(CFLAGS) -DP7_EMIT_MAIN -o trace/p7_emit trace/pack_row.c $(LIB_SRCS) lib/sha256.c

bins_probe:
	$(CC) $(CFLAGS) -o q3_probe/admit_run q3_probe/admit_run.c lib/epoch_chain.c

tools: bins_d0 bins_stages bins_trace bins_probe
	chmod +x tools/j4_round tools/p7_emit q3_probe/host_shell.sh q3_probe/work_shell.sh

clean:
	rm -f d0/j4_assemble d0/stg_u4 d0/stg_m1 d0/stg_p5 d0/tick_apply d0/witness_refresh trace/p7_emit q3_probe/admit_run
