#include <cstdio>
#include <fstream>
#include <string>

void format_link_phases(const char* env_root) {
    (void)env_root;
    std::printf("phase:open\nphase:detached\n");
}
