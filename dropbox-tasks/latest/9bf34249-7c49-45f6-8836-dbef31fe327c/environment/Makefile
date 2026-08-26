GHC ?= ghc

.PHONY: all clean

all: bin/cnfprep

bin/cnfprep: src/Main.hs
	mkdir -p bin build
	$(GHC) -O2 src/Main.hs -outputdir build -o bin/cnfprep

clean:
	rm -rf bin build
