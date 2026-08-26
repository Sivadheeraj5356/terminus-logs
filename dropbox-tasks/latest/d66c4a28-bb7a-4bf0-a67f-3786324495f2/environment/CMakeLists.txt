cmake_minimum_required(VERSION 3.16)
project(derive CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(OpenSSL REQUIRED)

add_executable(derive
    src/main.cpp
    src/spec_loader.cpp
    src/derive.cpp
    src/manifest.cpp
)

target_include_directories(derive PRIVATE src)
target_link_libraries(derive PRIVATE OpenSSL::Crypto)
target_compile_options(derive PRIVATE -Wall -Wextra)
