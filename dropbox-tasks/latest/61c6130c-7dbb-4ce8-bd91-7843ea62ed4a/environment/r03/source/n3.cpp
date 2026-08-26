#include "n3.hpp"

std::vector<NodeX> r08_flux(const GraphX& a, const std::vector<ItemX>& b) {
    std::vector<NodeX> out;
    for (const ItemX& item : b) {
        NodeX nd;
        nd.canon_pkg = item.raw_pkg;
        nd.comp = item.comp;
        auto found = a.sig.find(item.raw_pkg);
        nd.sig = found == a.sig.end() ? "" : found->second;
        nd.aliases.push_back(item.raw_pkg);
        out.push_back(nd);
    }
    return out;
}
