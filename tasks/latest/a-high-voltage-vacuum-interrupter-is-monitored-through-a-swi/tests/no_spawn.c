#define _GNU_SOURCE

#include <errno.h>
#include <spawn.h>
#include <stdio.h>
#include <sys/types.h>
#include <unistd.h>

static int denied(void) {
    errno = EPERM;
    return -1;
}

int system(const char *command) {
    (void)command;
    return denied();
}

FILE *popen(const char *command, const char *mode) {
    (void)command;
    (void)mode;
    errno = EPERM;
    return NULL;
}

pid_t fork(void) {
    errno = EPERM;
    return (pid_t)-1;
}

pid_t vfork(void) {
    errno = EPERM;
    return (pid_t)-1;
}

int execve(const char *path, char *const argv[], char *const envp[]) {
    (void)path;
    (void)argv;
    (void)envp;
    return denied();
}

int execv(const char *path, char *const argv[]) {
    (void)path;
    (void)argv;
    return denied();
}

int execvp(const char *file, char *const argv[]) {
    (void)file;
    (void)argv;
    return denied();
}

int execvpe(const char *file, char *const argv[], char *const envp[]) {
    (void)file;
    (void)argv;
    (void)envp;
    return denied();
}

int posix_spawn(pid_t *pid, const char *path,
                const posix_spawn_file_actions_t *actions,
                const posix_spawnattr_t *attributes,
                char *const argv[], char *const envp[]) {
    (void)pid;
    (void)path;
    (void)actions;
    (void)attributes;
    (void)argv;
    (void)envp;
    return EPERM;
}

int posix_spawnp(pid_t *pid, const char *file,
                 const posix_spawn_file_actions_t *actions,
                 const posix_spawnattr_t *attributes,
                 char *const argv[], char *const envp[]) {
    (void)pid;
    (void)file;
    (void)actions;
    (void)attributes;
    (void)argv;
    (void)envp;
    return EPERM;
}
