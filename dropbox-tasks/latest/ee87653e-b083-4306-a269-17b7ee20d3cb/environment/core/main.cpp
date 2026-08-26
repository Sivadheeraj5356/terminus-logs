#include "witness_bind.hpp"
#include "encoding_probe.hpp"
#include <iostream>

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cerr << "Usage: " << argv[0] << " <elf_library_path>" << std::endl;
        return 1;
    }

    std::string path = argv[1];
    std::cout << "Attesting ELF library: " << path << std::endl;

    reloc::EncodingProfile profile = reloc::probe_encoding_profile(path);
    switch (profile) {
        case reloc::EncodingProfile::ALPHA:
            std::cout << "Encoding profile: Alpha (witness-ready)" << std::endl;
            break;
        case reloc::EncodingProfile::BETA:
            std::cout << "Encoding profile: Beta (cipher-masked witness)" << std::endl;
            break;
        case reloc::EncodingProfile::GAMMA:
            std::cout << "Encoding profile: Gamma (envelope-packed witness)" << std::endl;
            break;
        case reloc::EncodingProfile::UNKNOWN:
            std::cerr << "Unknown encoding profile / policy refusal" << std::endl;
            return 1;
    }

    std::cout << "Binding relocation witness envelope..." << std::endl;
    if (reloc::bind_relocation_witness(path)) {
        std::cout << "Witness bind completed successfully." << std::endl;
        return 0;
    } else {
        std::cerr << "Failed to bind relocation witness." << std::endl;
        return 1;
    }
}
