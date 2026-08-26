CXX = g++
CXXFLAGS = -std=c++17 -Wall -Wextra -O2 -Iinclude
LDFLAGS =

SRCS = src/main.cpp src/cli.cpp src/json_io.cpp src/catalog.cpp src/normalize.cpp \
       src/row_overlap.cpp src/graph.cpp src/hash.cpp src/plan_builder.cpp \
       src/validate.cpp src/repair.cpp src/scan_cost.cpp src/fragmentation.cpp \
       src/replica.cpp src/partition.cpp src/report.cpp src/staging_io.cpp \
       src/ingest_chain.cpp src/ingest_stage.cpp src/export_stage.cpp src/span_rollup.cpp

OBJS = $(SRCS:.cpp=.o)

all: columnarctl

columnarctl: $(OBJS)
	$(CXX) $(CXXFLAGS) -o $@ $(OBJS) $(LDFLAGS)

%.o: %.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

clean:
	rm -f $(OBJS) columnarctl

.PHONY: all clean
