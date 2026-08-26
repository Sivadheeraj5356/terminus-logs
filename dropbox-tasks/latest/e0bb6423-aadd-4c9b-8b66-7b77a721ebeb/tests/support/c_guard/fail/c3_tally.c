#include "pamlink/tally.h"
#include "pamlink/cfg.h"
#include <string.h>

static int module_counted(const char *mod, char mods[][PL_NAME_MAX], int mod_n) {
    for (int i = 0; i < mod_n; i++) {
        if (strcmp(mods[i], mod) == 0) {
            return 1;
        }
    }
    return 0;
}

int c3_tally(const tape_event *ev, int n) {
    char mods[PL_MAX_MOD][PL_NAME_MAX];
    int mod_n = 0;
    if (cfg_load_count_modules(mods, PL_MAX_MOD, &mod_n) != 0 || mod_n == 0) {
        mod_n = 0;
        strncpy(mods[mod_n++], "pam_unix", PL_NAME_MAX - 1);
    }

    int tally = 0;
    for (int i = 0; i < n; i++) {
        if (strcmp(ev[i].result, "fail") == 0 && module_counted(ev[i].module, mods, mod_n)) {
            tally++;
        }
    }

    if (n > 0) {
        tally += cfg_read_ledger_failures(ev[0].actor);
    }
    return tally;
}
