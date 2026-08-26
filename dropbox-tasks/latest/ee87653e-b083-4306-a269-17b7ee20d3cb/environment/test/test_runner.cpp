#include <iostream>
#include <dlfcn.h>
#include <string>

typedef int (*compute_values_t)(int);
typedef const char* (*get_message_t)(int);

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cerr << "Usage: " << argv[0] << " <library_path>" << std::endl;
        return 1;
    }

    std::string lib_path = argv[1];
    std::cout << "Loading library: " << lib_path << std::endl;

    void* handle = dlopen(lib_path.c_str(), RTLD_NOW);
    if (!handle) {
        std::cerr << "Failed to load library: " << dlerror() << std::endl;
        return 2;
    }

    compute_values_t compute_values = (compute_values_t)dlsym(handle, "compute_values");
    get_message_t get_message = (get_message_t)dlsym(handle, "get_message");

    const char* dlsym_err = dlerror();
    if (dlsym_err || !compute_values || !get_message) {
        std::cerr << "Failed to find symbols: " << (dlsym_err ? dlsym_err : "symbols are null") << std::endl;
        dlclose(handle);
        return 3;
    }

    // Execute test cases
    std::cout << "Checking messages..." << std::endl;
    const char* msg0 = get_message(0);
    const char* msg1 = get_message(1);
    const char* msg2 = get_message(2);

    if (!msg0 || std::string(msg0) != "Hello from target lib!") {
        std::cerr << "Incorrect msg0" << std::endl;
        dlclose(handle);
        return 4;
    }
    if (!msg1 || std::string(msg1) != "Relocation reconstruction is successful.") {
        std::cerr << "Incorrect msg1" << std::endl;
        dlclose(handle);
        return 5;
    }
    if (!msg2 || std::string(msg2) != "Verification complete!") {
        std::cerr << "Incorrect msg2" << std::endl;
        dlclose(handle);
        return 6;
    }

    std::cout << "Running computations..." << std::endl;
    int res1 = compute_values(10);
    int res2 = compute_values(42);

    std::cout << "Result 1: " << res1 << std::endl;
    std::cout << "Result 2: " << res2 << std::endl;

    if (res1 <= 0 || res2 <= 0) {
        std::cerr << "Invalid computation results" << std::endl;
        dlclose(handle);
        return 7;
    }

    dlclose(handle);
    std::cout << "Library test completed successfully!" << std::endl;
    return 0;
}
