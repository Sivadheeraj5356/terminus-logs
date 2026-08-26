#ifndef MAZE_PATCH_H
#define MAZE_PATCH_H

#include "maze/model.h"

int maze_select_level(const maze_config *config, const maze_store *store,
                      json_t **level, json_t **provenance);

#endif
