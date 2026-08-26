GNATMAKE ?= gnatmake
GNATCOLL_INCLUDE ?= /usr/share/ada/adainclude/gnatcoll

channelgate: src/channelgate.adb src/admission_rules.adb src/wire.adb src/channels.adb
	mkdir -p build
	$(GNATMAKE) -q -O2 -Isrc -I$(GNATCOLL_INCLUDE) -D build \
	    -o $(CURDIR)/channelgate src/channelgate.adb \
	    -largs -L/usr/lib/x86_64-linux-gnu -lgnatcoll

clean:
	rm -rf build channelgate
