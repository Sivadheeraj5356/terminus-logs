#ifndef BOOT_ERA_H
#define BOOT_ERA_H

#define BOOT_ERA_PATH "/app/output/step/boot_era.rec"

int boot_era_read(const char *path);
int boot_era_write(const char *path, int era);
int boot_era_bump(const char *path);

#endif
