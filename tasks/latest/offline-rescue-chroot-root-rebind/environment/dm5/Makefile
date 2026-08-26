CC ?= gcc
CFLAGS ?= -Wall -Wextra -O2 -Iinclude
AR ?= ar

SRCS = src/bind_r1.c src/stub_dm.c
OBJS = $(SRCS:.c=.o)

all: libdm5.a

libdm5.a: $(OBJS)
	$(AR) rcs $@ $(OBJS)

clean:
	rm -f $(OBJS) libdm5.a

.c.o:
	$(CC) $(CFLAGS) -c $< -o $@
