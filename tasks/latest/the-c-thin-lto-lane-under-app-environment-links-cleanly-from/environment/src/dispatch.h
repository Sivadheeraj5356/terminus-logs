#pragma once

#include "plugin_iface.h"

template <int Seed>
struct SeededDispatch final : DispatchIface {
    int lane_id() const override { return Seed % 97; }
    int apply(int value) const override { return value + Seed + lane_id(); }
};
