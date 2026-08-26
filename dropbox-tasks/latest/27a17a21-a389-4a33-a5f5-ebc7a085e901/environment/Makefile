.PHONY: all clean run verify serve

all: run verify

DATA_FILE = dataset.csv

trace_ext.so: trace_ext.c
	gcc -shared -fPIC -I/usr/include/lua5.4 -o trace_ext.so trace_ext.c

$(DATA_FILE):
	python3 mock_server.py 8888 & echo $$! > server.pid; sleep 1
	if [ -z "$$NO_FETCH" ]; then curl -s http://localhost:8888/iris.csv -o $(DATA_FILE); fi
	kill `cat server.pid` || true; rm -f server.pid

run: $(DATA_FILE) trace_ext.so
	lua5.4 main.lua $(DATA_FILE)

verify: run
	duckdb iris.duckdb < verify.sql

clean:
	rm -f dataset.csv iris.duckdb server.pid insert_results.sql temp.csv trace_ext.so
