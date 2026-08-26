#include "pamlink/tapeio.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int parse_event(const char *line, tape_event *ev) {
    const char *p;
    if ((p = strstr(line, "\"seq\"")) == NULL) return -1;
    ev->seq = atoi(p + 6);
    if ((p = strstr(line, "\"ts\"")) == NULL) return -1;
    ev->ts = atoll(p + 5);
    if ((p = strstr(line, "\"actor\"")) == NULL) return -1;
    sscanf(p, "\"actor\": \"%127[^\"]\"", ev->actor);
    if ((p = strstr(line, "\"module\"")) == NULL) return -1;
    sscanf(p, "\"module\": \"%127[^\"]\"", ev->module);
    if ((p = strstr(line, "\"result\"")) == NULL) return -1;
    sscanf(p, "\"result\": \"%15[^\"]\"", ev->result);
    if ((p = strstr(line, "\"service\"")) == NULL) return -1;
    sscanf(p, "\"service\": \"%127[^\"]\"", ev->service);
    return 0;
}

int tape_read(const char *path, tape_event *out, int max, int *count) {
    FILE *f = fopen(path, "r");
    if (!f) return -1;
    char line[512];
    *count = 0;
    while (fgets(line, sizeof(line), f) && *count < max) {
        if (line[0] == '\n' || line[0] == '\0') continue;
        if (parse_event(line, &out[*count]) == 0) {
            (*count)++;
        }
    }
    fclose(f);
    return *count > 0 ? 0 : -1;
}
