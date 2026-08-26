SUBDIRS = bx7 lw3 dm5 tools/rk_pack tools/arena_ctl

.PHONY: all clean
all:
	@for d in $(SUBDIRS); do $(MAKE) -C $$d; done

clean:
	@for d in $(SUBDIRS); do $(MAKE) -C $$d clean; done
