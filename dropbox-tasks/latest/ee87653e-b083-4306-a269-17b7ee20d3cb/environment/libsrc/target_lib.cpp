#include <cstdio>
#include <cstring>
#include <cstdlib>

// Global pointers to string literals.
// These generate R_X86_64_RELATIVE relocations because the pointers need to be adjusted at load time.
const char* const global_messages[] = {
    "Hello from target lib!",
    "Relocation reconstruction is successful.",
    "Verification complete!"
};

extern "C" {

int compute_values(int input) {
    int sum = 0;
    
    // Call dynamic external symbols to trigger R_X86_64_JUMP_SLOT relocations
    char* buffer = (char*)std::malloc(64);
    if (!buffer) return -1;
    
    std::snprintf(buffer, 64, "%s %d", global_messages[1], input);
    size_t len = std::strlen(buffer);
    for (size_t i = 0; i < len; ++i) {
        sum += buffer[i];
    }
    
    std::free(buffer);
    return sum + input * 3;
}

const char* get_message(int index) {
    if (index >= 0 && index < 3) {
        return global_messages[index];
    }
    return nullptr;
}

}
