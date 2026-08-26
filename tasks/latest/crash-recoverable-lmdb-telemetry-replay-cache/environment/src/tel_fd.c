#include "tel_fd.h"

#include <dirent.h>
#include <errno.h>
#include <stdio.h>
#include <unistd.h>

int tel_count_open_fds(void) {
    char path[64];
    snprintf(path, sizeof(path), "/proc/%d/fd", getpid());
    DIR *dir = opendir(path);
    if (!dir) {
        return -1;
    }
    int count = 0;
    struct dirent *ent;
    while ((ent = readdir(dir)) != NULL) {
        if (ent->d_name[0] == '.') {
            continue;
        }
        count++;
    }
    closedir(dir);
    return count;
}
