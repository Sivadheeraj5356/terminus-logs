# SPDX-License-Identifier: MIT
BUILD = build
CC = gcc
CFLAGS = -Wall -Wextra -O2 -std=c11 -Iinclude -I.

SRCS = \
	n8_host/main.c \
	harness/h2_replay.c \
	harness/h5_fold.c \
	harness/h3_wait.c \
	harness/h4_emit.c \
	l4/l4_admit.c \
	l4/l4_log.c \
	stamp/s5_fold.c \
	stamp/s5_hist.c \
	wait/w6_hold.c \
	wait/w6_len.c \
	m7/m7_snap.c \
	m7/m7_count.c \
	persist/j4_lane.c

OBJS = $(patsubst %.c,$(BUILD)/%.o,$(SRCS))

$(BUILD)/bin/n8_host: $(OBJS)
	@mkdir -p $(BUILD)/bin
	$(CC) $(CFLAGS) -o $@ $(OBJS)

$(BUILD)/%.o: %.c
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -rf $(BUILD)

.PHONY: clean
