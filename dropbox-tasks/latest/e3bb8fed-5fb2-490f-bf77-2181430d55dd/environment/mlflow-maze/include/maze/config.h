#ifndef MAZE_CONFIG_H
#define MAZE_CONFIG_H

#include "maze/model.h"

int maze_config_load(const char *yaml_path, const char *toml_path,
                     maze_config *config);

#endif
