#ifndef SCENARIO_DEVICE_H
#define SCENARIO_DEVICE_H

#include "dm5_api.h"

int scenario_device_manifest(dm5_ctx *ctx, const backend_spec *spec, dev_epoch_t epoch, uint32_t gen);

#endif
