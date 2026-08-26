#include "tel_cli.h"
#include "tel_config.h"

#include <stdio.h>

int main(int argc, char **argv) {
    if (tel_config_init("/app/config/replayer.toml") != 0) {
        fprintf(stderr, "failed to load replayer config\n");
        return 2;
    }
    if (tel_config_validate_loaded() != 0) {
        fprintf(stderr, "invalid replayer config\n");
        tel_config_shutdown();
        return 2;
    }
    int rc = tel_cli_run(argc, argv);
    tel_config_shutdown();
    return rc;
}
