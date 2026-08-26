APP = parcel-access-gateway

.PHONY: all clean test

all: bin/$(APP)

bin/$(APP):
	mkdir -p bin
	GOTOOLCHAIN=local GOPROXY=off CGO_ENABLED=0 go build -o bin/$(APP) .

clean:
	rm -rf bin

test: all
	./bin/$(APP) testdata/happy.script > /tmp/$(APP).out
	grep -q "happy_080 ALLOW 80" /tmp/$(APP).out
