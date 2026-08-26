CC ?= cc
CFLAGS ?= -g -O0 -fno-omit-frame-pointer -Wall

vaultseal: vaultseal.c
	$(CC) $(CFLAGS) -o $@ $<

.PHONY: clean
clean:
	rm -f vaultseal
