#include <cstdio>
#include <fstream>
#include <string>

void print_quick_label(const char* audit_path) {
    std::ifstream in(audit_path);
    std::string text((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
    if (text.find("\"conv_label\": \"settled\"") != std::string::npos) {
        std::printf("settled 1\n");
        return;
    }
    std::printf("drift 0\n");
}
