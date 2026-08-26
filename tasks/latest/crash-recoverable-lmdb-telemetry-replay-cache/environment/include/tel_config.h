#ifndef TEL_CONFIG_H
#define TEL_CONFIG_H

#include <stdint.h>

int tel_config_init(const char *path);
uint64_t tel_config_window_ns(const char *scenario_id);
int tel_config_validate_loaded(void);
void tel_config_shutdown(void);

#endif
