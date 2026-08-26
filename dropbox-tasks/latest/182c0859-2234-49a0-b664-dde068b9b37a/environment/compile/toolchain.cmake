set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O2 -flto=thin -fPIC")
set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -flto=thin -fuse-ld=lld")
