#include "anchor.h"
#include "consumer.h"
#include "dispatch.h"
#include "gate_abi.h"

#include <iostream>
#include <memory>
#include <string>

static int run_probe() {
    std::unique_ptr<DispatchIface> iface(make_dispatch(GATE_DISPATCH_SEED));
    const int lane = iface->lane_id();
    const int mixed = iface->apply(anchor_lane());
    const std::string token = consumer_token(lane, gate_abi_tag());
    std::cout << token << " mixed=" << mixed << "\n";
    return 0;
}

int main(int argc, char **argv) {
    if (argc > 1 && std::string(argv[1]) == "--probe") {
        return run_probe();
    }
    std::cout << "matrix_app ready\n";
    return 0;
}
