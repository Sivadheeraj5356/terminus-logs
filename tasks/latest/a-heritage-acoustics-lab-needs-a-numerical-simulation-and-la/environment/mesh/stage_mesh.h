#ifndef STAGE_MESH_H
#define STAGE_MESH_H

#include "ac_types.h"

/* Persist cavity mesh staging under /app/state/<profile>/cavity_mesh.json */
int stage_mesh_write(const char *profile, const ac_ct_volume *vol, const ac_speed_map *speed);
int stage_mesh_read_digest(const char *profile, char *out_hex, int out_len);
int stage_mesh_speed_digest(const ac_speed_map *speed, char *out_hex, int out_len);

#endif
