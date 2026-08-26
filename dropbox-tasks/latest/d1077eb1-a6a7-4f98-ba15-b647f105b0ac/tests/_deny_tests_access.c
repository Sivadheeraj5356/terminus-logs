#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

static int blocked_path(const char *path) {
    if (path == NULL) {
        return 0;
    }
    if (strncmp(path, "/tests", 6) == 0 && (path[6] == '\0' || path[6] == '/')) {
        return 1;
    }
    if (strstr(path, "test_outputs") != NULL) {
        return 1;
    }
    return 0;
}

static int blocked_exec(const char *path) {
    const char *base;
    if (path == NULL) {
        return 0;
    }
    base = strrchr(path, '/');
    base = base ? base + 1 : path;
    if (strcmp(base, "python") == 0 || strcmp(base, "python3") == 0) {
        return 1;
    }
    if (strncmp(base, "python3.", 8) == 0) {
        return 1;
    }
    return 0;
}

int open(const char *pathname, int flags, ...) {
    static int (*real_open)(const char *, int, ...) = NULL;
    mode_t mode = 0;
    if (!real_open) {
        real_open = (int (*)(const char *, int, ...))dlsym(RTLD_NEXT, "open");
    }
    if (blocked_path(pathname)) {
        errno = EACCES;
        return -1;
    }
    if (flags & O_CREAT) {
        va_list ap;
        va_start(ap, flags);
        mode = (mode_t)va_arg(ap, int);
        va_end(ap);
        return real_open(pathname, flags, mode);
    }
    return real_open(pathname, flags);
}

int openat(int dirfd, const char *pathname, int flags, ...) {
    static int (*real_openat)(int, const char *, int, ...) = NULL;
    mode_t mode = 0;
    if (!real_openat) {
        real_openat = (int (*)(int, const char *, int, ...))dlsym(RTLD_NEXT, "openat");
    }
    if (blocked_path(pathname)) {
        errno = EACCES;
        return -1;
    }
    if (flags & O_CREAT) {
        va_list ap;
        va_start(ap, flags);
        mode = (mode_t)va_arg(ap, int);
        va_end(ap);
        return real_openat(dirfd, pathname, flags, mode);
    }
    return real_openat(dirfd, pathname, flags);
}

FILE *fopen(const char *pathname, const char *mode) {
    static FILE *(*real_fopen)(const char *, const char *) = NULL;
    if (!real_fopen) {
        real_fopen = (FILE *(*)(const char *, const char *))dlsym(RTLD_NEXT, "fopen");
    }
    if (blocked_path(pathname)) {
        errno = EACCES;
        return NULL;
    }
    return real_fopen(pathname, mode);
}

int execve(const char *pathname, char *const argv[], char *const envp[]) {
    static int (*real_execve)(const char *, char *const[], char *const[]) = NULL;
    if (!real_execve) {
        real_execve = (int (*)(const char *, char *const[], char *const[]))dlsym(RTLD_NEXT, "execve");
    }
    if (blocked_exec(pathname) || blocked_path(pathname)) {
        errno = EACCES;
        return -1;
    }
    return real_execve(pathname, argv, envp);
}
