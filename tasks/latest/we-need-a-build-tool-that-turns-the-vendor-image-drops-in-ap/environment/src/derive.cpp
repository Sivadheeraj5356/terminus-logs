#include "derive.hpp"
#include <stdexcept>

DerivativeResult produce_derivative(
    const std::string& source_path,
    const AssetClassRule& rule,
    const std::string& out_dir
) {
    // TODO: auto-orient, apply cover/fit per rule, handle ICC policy,
    // write the derivative deterministically, hash the result.
    (void)source_path;
    (void)rule;
    (void)out_dir;
    throw std::runtime_error("not implemented");
}
