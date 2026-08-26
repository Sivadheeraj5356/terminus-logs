#include <stdio.h>
#include <string.h>

void report_hour_table(const char *zone) {
    FILE *fp = fopen("/app/environment/n2h/missing_hours.tab", "r");
    int rows = 0;
    if (fp) {
        char line[128];
        while (fgets(line, sizeof line, fp)) {
            if (line[0] == '#' || line[0] == '\n') {
                continue;
            }
            rows++;
        }
        fclose(fp);
    }
    fprintf(stderr, "hour-table zone=%s rows=%d\n", zone ? zone : "?", rows);
}
