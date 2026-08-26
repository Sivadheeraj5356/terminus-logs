#include <stdio.h>

void lane_log_fd(int fd)
{
    fprintf(stderr, "lane fd=%d\n", fd);
}
