BUILD = build
CC = gcc
CFLAGS = -Wall -Wextra -O2 -std=c11 -D_POSIX_C_SOURCE=200809L \
	-Iinclude -Ilib -Imask -Ibound -Ilane -Is6_host -Igate -Iload -Iprobe -Isnap -Istate

LIB_SRCS = \
	lib/sha256.c \
	lib/tag_from.c \
	mask/k5_row.c \
	mask/k5_log.c \
	bound/h2_cap.c \
	bound/h2_len.c \
	lane/m3_fd.c \
	lane/m3_log.c \
	s6_host/s6_emit.c \
	s6_host/s6_count.c \
	gate/r9_peer.c \
	gate/r9_alt.c \
	gate/r9_prep.c \
	load/l1_load.c \
	probe/d8_read.c \
	snap/n3_snap.c \
	state/k4_epoch.c \
	state/k4_carry.c

LIB_OBJS = $(patsubst %.c,$(BUILD)/%.o,$(LIB_SRCS))

$(BUILD)/%.o: %.c
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/libd8.a: $(LIB_OBJS)
	ar rcs $@ $(LIB_OBJS)

$(BUILD)/h2_runner: tools/h2_main.c $(BUILD)/libd8.a
	$(CC) $(CFLAGS) -o $@ tools/h2_main.c $(BUILD)/libd8.a

$(BUILD)/q1_emit: tools/q1_main.c $(BUILD)/libd8.a
	$(CC) $(CFLAGS) -o $@ tools/q1_main.c $(BUILD)/libd8.a

$(BUILD)/t11_host: t11_host/main.c $(BUILD)/libd8.a
	$(CC) $(CFLAGS) -o $@ t11_host/main.c $(BUILD)/libd8.a

all: $(BUILD)/h2_runner $(BUILD)/q1_emit $(BUILD)/t11_host
	@mkdir -p /app/tools 2>/dev/null || true
	@cp $(BUILD)/h2_runner /app/tools/h2_runner 2>/dev/null || true
	@cp $(BUILD)/q1_emit /app/tools/q1_emit 2>/dev/null || true

clean:
	rm -rf $(BUILD)

.PHONY: all clean
