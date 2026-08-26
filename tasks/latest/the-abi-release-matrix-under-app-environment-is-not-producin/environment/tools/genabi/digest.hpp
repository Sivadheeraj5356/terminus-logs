#ifndef GENABI_DIGEST_HPP
#define GENABI_DIGEST_HPP

#include <cstdint>
#include <string>

// Rolling 64-bit mixer used to fingerprint the ordered IDL inputs.
class Mixer {
public:
    void mix_u64(const std::string &text);
    void mix_u64(const unsigned char *data, std::size_t len);
    std::string hex() const;

private:
    std::uint64_t state_ = 1469598103934665603ULL;
};

// Fingerprint of the ordered IDL bundle plus the lane label.
std::string idl_digest(const std::string &idl_dir, const std::string &label);

#endif
