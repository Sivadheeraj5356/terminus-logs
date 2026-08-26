#ifndef FOLDPATH_CONFIG_H
#define FOLDPATH_CONFIG_H

#include "foldpath/types.h"

fp_result fp_model_load(const char *path, fp_model *model, uint64_t *fingerprint);
fp_result fp_control_load(const char *path, fp_control *control, uint64_t *fingerprint);
const char *fp_model_kind_name(fp_model_kind kind);

#endif
