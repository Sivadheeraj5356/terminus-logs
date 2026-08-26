CC ?= gcc
CFLAGS ?= -Wall -Wextra -O2 -I../../bx7/include -I../../lw3/include -I../../dm5/include -Isrc
LDFLAGS ?= -lcrypto

ROOT = ../..
LIBS = $(ROOT)/bx7/libbx7.a $(ROOT)/lw3/liblw3.a $(ROOT)/dm5/libdm5.a

all: rk_pack

rk_pack: src/main.o src/engine.o src/scenario_root.o src/scenario_linker.o src/scenario_device.o $(LIBS)
	$(CC) $(CFLAGS) -o $@ src/main.o src/engine.o src/scenario_root.o src/scenario_linker.o src/scenario_device.o $(LIBS) $(LDFLAGS)

src/%.o: src/%.c
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -f src/*.o rk_pack

$(LIBS):
	$(MAKE) -C $(ROOT)/bx7
	$(MAKE) -C $(ROOT)/lw3
	$(MAKE) -C $(ROOT)/dm5
