#include "dispatch.h"

#include "gate_abi.h"

DispatchIface *make_dispatch(int seed) {
    const int active = (seed > 0) ? seed : GATE_DISPATCH_SEED;
    switch (active % 4) {
    case 0:
        return new SeededDispatch<11>();
    case 1:
        return new SeededDispatch<29>();
    case 2:
        return new SeededDispatch<47>();
    default:
        return new SeededDispatch<71>();
    }
}
