CXX = g++
CXXFLAGS = -std=c++17 -Wall -Wextra -O1 -Iinclude
LDFLAGS =

SRC_DIR = src
BIN_DIR = bin
TARGET = $(BIN_DIR)/vlan-segmentation-enforce

SRCS = $(wildcard $(SRC_DIR)/*.cpp)
OBJS = $(SRCS:.cpp=.o)

.PHONY: all clean

all: $(TARGET)

$(TARGET): $(SRCS) | $(BIN_DIR)
	$(CXX) $(CXXFLAGS) $(LDFLAGS) -o $@ $(SRCS)

$(BIN_DIR):
	mkdir -p $(BIN_DIR)

clean:
	rm -rf $(BIN_DIR) $(SRC_DIR)/*.o
