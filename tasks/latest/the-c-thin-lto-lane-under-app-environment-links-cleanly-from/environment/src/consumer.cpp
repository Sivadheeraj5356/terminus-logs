#include "consumer.h"

#include "gate_abi.h"

#include <sstream>
#include <string>

std::string consumer_token(int lane, const char *abi_tag) {
    std::ostringstream out;
    out << "lane=" << lane << " abi=" << abi_tag << " seed=" << GATE_DISPATCH_SEED;
    return out.str();
}
