NODE ?= node

# Native type-stripping build: type-check-free strip of the TypeScript entry
# point, then a syntax check so a broken source fails the build. The runnable
# artifact is the checked-in TypeScript run through node --experimental-strip-types
# by the isoreg launcher; the build produces a marker once the entry parses.
dist/isoreg.built: src/main.ts src/isotonic.ts
	mkdir -p dist
	$(NODE) --experimental-strip-types --check src/main.ts
	$(NODE) --experimental-strip-types --check src/isotonic.ts
	touch dist/isoreg.built

.PHONY: clean
clean:
	rm -f dist/isoreg.built
