CC ?= gcc
CFLAGS ?= -Wall -Wextra -O2 -Iinclude
AR ?= ar

SRCS = src/step_q2.c src/stub_qx.c
OBJS = $(SRCS:.c=.o)

all: libbx7.a

libbx7.a: $(OBJS)
	$(AR) rcs $@ $(OBJS)

clean:
	rm -f $(OBJS) libbx7.a

.c.o:
	$(CC) $(CFLAGS) -c $< -o $@
