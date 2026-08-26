#pragma once

struct DispatchIface {
    virtual int lane_id() const = 0;
    virtual int apply(int value) const = 0;
    virtual ~DispatchIface() = default;
};

DispatchIface *make_dispatch(int seed);
