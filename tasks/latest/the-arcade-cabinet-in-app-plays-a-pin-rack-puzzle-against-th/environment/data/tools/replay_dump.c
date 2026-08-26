#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void draw(int n)
{
    int i;
    if (n <= 0) {
        printf("(clear)");
        return;
    }
    for (i = 0; i < n && i < 60; i++) putchar('!');
    if (n > 60) printf(" +%d", n - 60);
}

int main(int argc, char **argv)
{
    FILE *fp;
    char line[256];

    if (argc < 2) {
        fprintf(stderr, "usage: replay_dump <replay.log>\n");
        return 1;
    }
    fp = fopen(argv[1], "r");
    if (!fp) {
        perror(argv[1]);
        return 1;
    }
    while (fgets(line, sizeof(line), fp)) {
        char key[32];
        if (sscanf(line, "%31s", key) != 1) continue;
        if (!strcmp(key, "STATE")) {
            int dial = 0, latch = 0, a = 0, b = 0;
            int got = sscanf(line, "%*s %*s %d %*s %d %*s %d %d", &dial, &latch, &a, &b);
            printf("  dial %d  latch %d  |  ", dial, latch);
            if (got >= 3) draw(a);
            else draw(0);
            if (got >= 4) {
                printf("   /   ");
                draw(b);
            }
            putchar('\n');
        } else if (!strcmp(key, "THROW")) {
            char who[16];
            int lane = 0, pins = 0, split = 0;
            sscanf(line, "%*s %15s %d %d %d", who, &lane, &pins, &split);
            printf("%-6s lane %d takes %d%s\n", who, lane, pins,
                   split ? " and breaks the row" : "");
        } else if (!strcmp(key, "START") || !strcmp(key, "WINNER") ||
                   !strcmp(key, "ATTRACT")) {
            fputs(line, stdout);
        }
    }
    fclose(fp);
    return 0;
}
