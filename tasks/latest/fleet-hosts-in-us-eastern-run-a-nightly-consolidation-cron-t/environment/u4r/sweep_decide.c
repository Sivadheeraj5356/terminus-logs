#include "../src/boot_era.h"

#include <stdio.h>

int decide_sweep(const char *frag_path, int boot_gap, int recovery_mode, int *exec_out) {
    (void)frag_path;
    if (!exec_out) {
        return -1;
    }
    if (!boot_gap) {
        *exec_out = 0;
        return 0;
    }
    if (!recovery_mode) {
        *exec_out = 1;
        return 0;
    }
    if (boot_era_read(BOOT_ERA_PATH) < 1) {
        *exec_out = 0;
        return 0;
    }
    *exec_out = 1;
    return 0;
}
