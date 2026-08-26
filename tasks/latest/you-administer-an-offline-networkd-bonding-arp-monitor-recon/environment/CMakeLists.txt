cmake_minimum_required(VERSION 3.16)
project(networkd_bond_reconcile CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include_directories(${CMAKE_SOURCE_DIR}/include)

set(VX_SOURCES
    include/vx_md5.cpp
    p3k/src/tbl_mux.cpp
    p3k/src/tbl_help.cpp
    q7n/src/gen_mux.cpp
    t2w/src/ord_mux.cpp
    t2w/src/ord_decoy.cpp
    u8m/src/jrnl_mux.cpp
    v5r/src/bind_mux.cpp
    x1h/src/seal_mux.cpp
    w4z/src/view_mux.cpp
    n9p/src/arp_mux.cpp
    g6k/src/gate_mux.cpp
    k7r/src/chain_mux.cpp
    engine/src/ph_common.cpp
    engine/src/ph_chain.cpp
    engine/src/ph_peer.cpp
    engine/src/ph_ord.cpp
    engine/src/ph_gen.cpp
    engine/src/ph_fp.cpp
    engine/src/ph_arp.cpp
    engine/src/ph_merge.cpp
    engine/src/ph_gate.cpp
    engine/src/phase_mux.cpp
    engine/src/ph_emit.cpp
    engine/src/sync_q2m.cpp
    engine/src/main.cpp
)

add_executable(vx_bond ${VX_SOURCES})
target_compile_options(vx_bond PRIVATE -Wall -Wextra)

add_executable(bond_probe
    tools/bond_probe/main.cpp
    w4z/src/view_mux.cpp
    include/vx_md5.cpp
)
target_compile_options(bond_probe PRIVATE -Wall -Wextra)
target_include_directories(bond_probe PRIVATE ${CMAKE_SOURCE_DIR}/include)
