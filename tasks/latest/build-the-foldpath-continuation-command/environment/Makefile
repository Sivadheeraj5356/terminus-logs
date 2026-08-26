CC ?= cc
AR ?= ar
INSTALL ?= install

CPPFLAGS ?= -Iinclude
CFLAGS ?= -std=c11 -O2 -g -Wall -Wextra -Wpedantic -Werror
LDFLAGS ?=
LDLIBS ?= -lm

BUILD_DIR := build
CORE_SOURCES := \
	src/config.c \
	src/fingerprint.c \
	src/linear.c \
	src/model.c \
	src/output.c \
	src/path.c \
	src/state.c
CORE_OBJECTS := $(patsubst src/%.c,$(BUILD_DIR)/%.o,$(CORE_SOURCES))
CHECK_OBJECT := $(BUILD_DIR)/check_main.o
EXTRA_SOURCES := $(filter-out $(CORE_SOURCES) src/check_main.c,$(wildcard src/*.c))
EXTRA_OBJECTS := $(patsubst src/%.c,$(BUILD_DIR)/%.o,$(EXTRA_SOURCES))
DEPENDENCIES := $(CORE_OBJECTS:.o=.d) $(CHECK_OBJECT:.o=.d) $(EXTRA_OBJECTS:.o=.d)

ALL_TARGETS := $(BUILD_DIR)/libfoldpath.a $(BUILD_DIR)/foldmodel-check
ifneq ($(strip $(EXTRA_SOURCES)),)
ALL_TARGETS += $(BUILD_DIR)/foldpath
endif

.PHONY: all clean install smoke

all: $(ALL_TARGETS)

$(BUILD_DIR):
	mkdir -p $@

$(BUILD_DIR)/%.o: src/%.c | $(BUILD_DIR)
	$(CC) $(CPPFLAGS) $(CFLAGS) -MMD -MP -c $< -o $@

$(BUILD_DIR)/libfoldpath.a: $(CORE_OBJECTS)
	$(AR) rcs $@ $^

$(BUILD_DIR)/foldmodel-check: $(CHECK_OBJECT) $(BUILD_DIR)/libfoldpath.a
	$(CC) $(LDFLAGS) -o $@ $(CHECK_OBJECT) $(BUILD_DIR)/libfoldpath.a $(LDLIBS)

ifneq ($(strip $(EXTRA_SOURCES)),)
$(BUILD_DIR)/foldpath: $(EXTRA_OBJECTS) $(BUILD_DIR)/libfoldpath.a
	$(CC) $(LDFLAGS) -o $@ $(EXTRA_OBJECTS) $(BUILD_DIR)/libfoldpath.a $(LDLIBS)
endif

install: all
	$(INSTALL) -d /usr/local/bin
	$(INSTALL) -m 0755 $(BUILD_DIR)/foldmodel-check /usr/local/bin/foldmodel-check
ifneq ($(strip $(EXTRA_SOURCES)),)
	$(INSTALL) -m 0755 $(BUILD_DIR)/foldpath /usr/local/bin/foldpath
endif

smoke: all
	./scripts/smoke.sh

clean:
	rm -rf $(BUILD_DIR)

-include $(DEPENDENCIES)
