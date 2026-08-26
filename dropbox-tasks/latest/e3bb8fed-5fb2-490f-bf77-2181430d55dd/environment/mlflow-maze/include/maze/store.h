#ifndef MAZE_STORE_H
#define MAZE_STORE_H

#include "maze/model.h"

int maze_store_open(const char *path, const maze_config *config,
                    maze_store **store);
void maze_store_close(maze_store *store);

#endif
