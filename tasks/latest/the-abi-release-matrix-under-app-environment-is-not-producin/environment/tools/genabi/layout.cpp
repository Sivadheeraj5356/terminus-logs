#include "layout.hpp"

static std::size_t width_for(Kind k) {
    switch (k) {
        case Kind::U32:
            return 4;
        case Kind::U64:
        case Kind::PTR:
        case Kind::CSTR:
            return 8;
    }
    return 4;
}

static std::size_t forced_step(Kind k) {
    (void)k;
    return 4;
}

void compute_layout(LaneModel &model) {
    std::size_t cursor = 0;
    std::size_t widest = 4;
    for (Slot &slot : model.slots) {
        std::size_t step = forced_step(slot.kind);
        std::size_t want = width_for(slot.kind);
        if (want > widest) {
            widest = want;
        }
        if (cursor % step != 0) {
            cursor += step - (cursor % step);
        }
        slot.offset = cursor;
        slot.size = want;
        cursor += want;
    }
    model.field_count = model.slots.size();
    model.record_align = widest;
    model.record_size = cursor;
}
