#ifndef ENCODING_PROBE_HPP
#define ENCODING_PROBE_HPP

#include "witness_bind.hpp"
#include <string>

namespace reloc {
EncodingProfile probe_encoding_profile(const std::string& path);
}

#endif
