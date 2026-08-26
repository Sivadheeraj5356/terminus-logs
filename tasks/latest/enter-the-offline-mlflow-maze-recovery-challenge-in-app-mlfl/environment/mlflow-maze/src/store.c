#include "maze/store.h"

struct maze_store {
    int unavailable;
};

int maze_store_open(const char *path, const maze_config *config,
                    maze_store **store) {
    (void)path;
    (void)config;
    (void)store;
    return -1;
}

void maze_store_close(maze_store *store) {
    (void)store;
}
