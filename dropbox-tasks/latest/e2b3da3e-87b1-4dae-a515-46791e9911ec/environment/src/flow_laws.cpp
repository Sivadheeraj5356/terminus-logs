#include "lockcore/flow_laws.hpp"
#include <cmath>
namespace lockcore {
double applyFlowCap(double q, double maximum_abs_flow_m3_s) {
    if (q > maximum_abs_flow_m3_s) return maximum_abs_flow_m3_s;
    if (q < -maximum_abs_flow_m3_s) return -maximum_abs_flow_m3_s;
    return q;
}
double gateFlow(double h_from, double h_to, double control, double discharge_coefficient, double area_m2,
                 double gravity_m_s2, double maximum_abs_flow_m3_s) {
    double delta_h = h_from - h_to;
    if (delta_h == 0.0) return 0.0;
    double K = control * discharge_coefficient * area_m2;
    double q = K * std::sqrt(2.0 * gravity_m_s2 * std::fabs(delta_h));
    return applyFlowCap(q, maximum_abs_flow_m3_s);
}
double weirFlow(double h_from, double h_to, double control, double discharge_coefficient, double width_m,
                 double crest_level_m, double maximum_abs_flow_m3_s) {
    double upstream_head = h_from - crest_level_m;
    if (!(upstream_head > 0.0)) return 0.0;
    (void)h_to;
    double q = control * discharge_coefficient * width_m * std::pow(upstream_head, 1.5);
    if (q < 0.0) q = 0.0;
    return applyFlowCap(q, maximum_abs_flow_m3_s);
}
double pumpFlow(double control, double maximum_abs_flow_m3_s) {
    return applyFlowCap(control, maximum_abs_flow_m3_s);
}
double linkFlow(const LinkSpec& link, double h_from, double h_to, double control, double gravity_m_s2) {
    switch (link.link_type) {
        case LinkType::Gate:
            return gateFlow(h_from, h_to, control, link.discharge_coefficient, link.area_m2, gravity_m_s2, link.maximum_abs_flow_m3_s);
        case LinkType::Weir:
            return weirFlow(h_from, h_to, control, link.discharge_coefficient, link.width_m, link.crest_level_m, link.maximum_abs_flow_m3_s);
        case LinkType::Pump:
            return pumpFlow(control, link.maximum_abs_flow_m3_s);
    }
    return 0.0;
}
}
