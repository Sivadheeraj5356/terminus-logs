#ifndef MAZE_REPLAY_H
#define MAZE_REPLAY_H

#include <jansson.h>

int maze_build_walkthrough(json_t *level, json_t **walkthrough);
int maze_replay_manifest(const char *manifest_path);

#endif
