#include <stddef.h>
#include <stdio.h>
#include <string.h>

static int lookup_hour(int hour_slot) {
    FILE *fp = fopen("/app/environment/n2h/missing_hours.tab", "r");
    if (!fp) {
        return 1;
    }
    char line[128];
    while (fgets(line, sizeof line, fp)) {
        if (line[0] == '#' || line[0] == '\n') {
            continue;
        }
        int hh = -1;
        int exists = 1;
        if (sscanf(line, "%d %d", &hh, &exists) == 2 && hh == hour_slot) {
            fclose(fp);
            return exists;
        }
    }
    fclose(fp);
    return 1;
}

int hour_exists(const char *zone, int hour_slot, int *exists_out) {
    (void)zone;
    if (!exists_out) {
        return -1;
    }
    int tab_exists = lookup_hour(hour_slot);
    *exists_out = tab_exists;
    if (!tab_exists) {
        return 1;
    }
    *exists_out = 1;
    return 0;
}
