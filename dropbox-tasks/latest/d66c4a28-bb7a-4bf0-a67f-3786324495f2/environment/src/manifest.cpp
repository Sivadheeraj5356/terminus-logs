#include "manifest.hpp"
#include <fstream>
#include <stdexcept>

void write_manifest(
    const std::string& manifest_path,
    const std::vector<DerivativeResult>& derivatives
) {
    // TODO: emit /app/out/manifest.json in the spec's schema and order.
    (void)derivatives;
    std::ofstream out(manifest_path);
    if (!out) throw std::runtime_error("cannot open manifest path");
    out << "{}\n";
}
