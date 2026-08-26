CC = gcc
CFLAGS = -std=c11 -Wall -Wextra -O2 -I.
LDFLAGS = -lcrypto

SRC_CORE = \
	m5s/next_fire.c m5s/fire_audit.c \
	n2h/hour_exists.c n2h/hour_report.c \
	u4r/sweep_decide.c u4r/sweep_tally.c \
	q8k/key_reconcile.c q8k/key_checksum.c \
	rowpack/row_fold.c rowpack/row_echo.c \
	src/commit_log.c src/boot_era.c src/lane_backward.c src/lane_forward.c src/lane_resume.c

OBJ_CORE = $(SRC_CORE:.c=.o)

BUILD = build
STEP_BIN = $(BUILD)/step_tool
PACK_BIN = $(BUILD)/pack_tool

.PHONY: all clean

all: $(BUILD) $(STEP_BIN) $(PACK_BIN)

$(BUILD):
	mkdir -p $(BUILD)

$(STEP_BIN): src/step_main.c $(OBJ_CORE) | $(BUILD)
	$(CC) $(CFLAGS) -o $@ src/step_main.c $(OBJ_CORE) $(LDFLAGS)

$(PACK_BIN): src/pack_main.c rowpack/row_fold.o | $(BUILD)
	$(CC) $(CFLAGS) -o $@ src/pack_main.c rowpack/row_fold.o $(LDFLAGS)

%.o: %.c
	$(CC) $(CFLAGS) -c -o $@ $<

clean:
	rm -rf $(BUILD) $(OBJ_CORE)
