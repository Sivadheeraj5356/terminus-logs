#include <stdio.h>
#include <string.h>

int main(void)
{
    char line[256];
    int called = 0;

    setvbuf(stdout, NULL, _IOLBF, 0);

    while (fgets(line, sizeof(line), stdin)) {
        if (!strncmp(line, "BYE", 3)) break;
        if (!strncmp(line, "RESULT", 6)) break;
        if (!strncmp(line, "HOUSE", 5)) continue;
        if (strncmp(line, "RACK", 4)) continue;

        if (!called) {
            called = 1;
            printf("CALL PLAY\n");
        }

        printf("THROW 1 1 0\n");
    }

    return 0;
}
