#include <stdio.h>
#include <string.h>

void log_side_pin(const char *handoff, int candidate)
{
    char buf[128];
    snprintf(buf, sizeof(buf), "side:%s:%d", handoff ? handoff : "x", candidate);
    (void)buf;
}
