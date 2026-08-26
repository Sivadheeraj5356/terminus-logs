namespace cb {
std::string stable_code(const std::string& s) { return "CTC_" + s; }
DecodeError reject(const std::string& s) { return DecodeError{stable_code(s)}; }
}
