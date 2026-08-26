cmake_minimum_required(VERSION 3.16)
project(cryoready CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(nlohmann_json 3.11 REQUIRED)
find_package(OpenSSL REQUIRED)

add_executable(cryoready
    src/main.cpp
    src/digest.cpp
    src/load.cpp
    src/fill.cpp
    src/hold.cpp
    src/pressure.cpp
    src/windows.cpp
    src/compat.cpp
    src/sensors.cpp
    src/inventory.cpp
    src/assess.cpp
    src/certificate.cpp
    src/ledger.cpp
)

target_include_directories(cryoready PRIVATE include src)
target_link_libraries(cryoready PRIVATE nlohmann_json::nlohmann_json OpenSSL::Crypto)

install(TARGETS cryoready RUNTIME DESTINATION bin)
