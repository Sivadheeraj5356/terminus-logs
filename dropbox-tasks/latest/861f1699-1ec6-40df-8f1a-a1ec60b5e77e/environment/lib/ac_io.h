#ifndef AC_IO_H
#define AC_IO_H

#include "ac_types.h"

int ac_read_ct_volume(const char *path, ac_ct_volume *vol);
int ac_write_pressure_wav(const char *path, const ac_pressure_trace *trace, int sr_hz);

#endif
