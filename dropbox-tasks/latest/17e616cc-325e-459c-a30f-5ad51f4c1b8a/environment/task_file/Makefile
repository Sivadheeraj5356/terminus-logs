.PHONY: all clean

all:
	mkdir -p /app/bin
	cd src && /usr/local/go/bin/go build -trimpath -o /app/bin/closure-plan .

clean:
	rm -f /app/bin/closure-plan
