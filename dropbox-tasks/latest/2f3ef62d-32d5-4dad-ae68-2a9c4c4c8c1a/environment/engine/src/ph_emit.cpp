#include "ph_iface.hpp"
#include "vx_types.hpp"

#include <string>

Row emit_row_phase(const std::string& env_root, const std::string& lane_id, int loc_rc, int img_rc,
                   int lag_code, const std::string& facet) {
    (void)env_root;
    Row row;
    row.lane_id = lane_id;
    row.loc_rc = loc_rc;
    row.img_rc = img_rc;
    row.bind_rc = 0;
    row.lag_code = lag_code;
    row.facet_hex = facet;
    return row;
}
