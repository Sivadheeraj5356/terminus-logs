#include "scenario_device.h"

int scenario_device_manifest(dm5_ctx *ctx, const backend_spec *spec, dev_epoch_t epoch, uint32_t gen) {
    return stamp_r1(ctx, spec, epoch, gen);
}
