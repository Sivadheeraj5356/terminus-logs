#include "span_rollup.h"

static uint32_t row_span(const Fragment& f) {
    return f.row_end >= f.row_start ? f.row_end - f.row_start + 1 : 0;
}

uint32_t chain_span_total(
    const std::vector<uint16_t>& order,
    const std::vector<int>& overlaps,
    const std::map<uint16_t, Fragment>& by_id) {
    if (order.empty()) return 0;
    uint32_t total = row_span(by_id.at(order[0]));
    for (size_t i = 1; i < order.size(); ++i) {
        const Fragment& next = by_id.at(order[i]);
        int ov = overlaps[i - 1];
        total += row_span(next) - static_cast<uint32_t>(ov);
    }
    return total;
}
