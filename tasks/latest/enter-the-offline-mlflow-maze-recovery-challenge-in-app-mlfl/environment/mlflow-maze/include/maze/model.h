#ifndef MAZE_MODEL_H
#define MAZE_MODEL_H

#include <jansson.h>

typedef struct maze_config {
    char *level_id;
    char *experiment_name;
    char *start_room;
    char *goal_room;
    char *directions[4];
    json_t *rooms;
    json_t *puzzles;
} maze_config;

typedef struct maze_store maze_store;

void maze_config_destroy(maze_config *config);

#endif
