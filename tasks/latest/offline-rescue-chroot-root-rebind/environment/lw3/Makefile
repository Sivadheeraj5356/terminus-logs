CC ?= gcc
CFLAGS ?= -Wall -Wextra -O2 -Iinclude
AR ?= ar

SRCS = src/phase_m4.c src/stub_lw.c
OBJS = $(SRCS:.c=.o)

all: liblw3.a

liblw3.a: $(OBJS)
	$(AR) rcs $@ $(OBJS)

clean:
	rm -f $(OBJS) liblw3.a

.c.o:
	$(CC) $(CFLAGS) -c $< -o $@
