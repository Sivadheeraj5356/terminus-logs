#include "maze/config.h"

int maze_config_load(const char *yaml_path, const char *toml_path,
                     maze_config *config) {
    (void)yaml_path;
    (void)toml_path;
    (void)config;
    return -1;
}

void maze_config_destroy(maze_config *config) {
    (void)config;
}
