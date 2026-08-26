// Vacuum-interrupter restrike reconstruction starter.

#include <cmath>
#include <cstdio>
#include <iostream>
#include <string>

static double read_number(const std::string &line, const std::string &key) {
    const std::string marker = "\"" + key + "\":";
    const std::size_t pos = line.find(marker);
    if (pos == std::string::npos) {
        return 0.0;
    }
    try {
        return std::stod(line.substr(pos + marker.size()));
    } catch (...) {
        return 0.0;
    }
}

static std::string number(double value) {
    char buffer[64];
    std::snprintf(buffer, sizeof(buffer), "%.9f", value);
    std::string text(buffer);
    while (!text.empty() && text.back() == '0') {
        text.pop_back();
    }
    if (!text.empty() && text.back() == '.') {
        text.pop_back();
    }
    return text.empty() ? "0" : text;
}

int main() {
    std::string config;
    if (!std::getline(std::cin, config)) {
        std::cout << "[]\n";
        return 0;
    }
    const double start = read_number(config, "window_start");
    const double end = read_number(config, "window_end");
    if (end <= start) {
        std::cout << "[]\n";
        return 0;
    }
    std::cout << "[{\"state\":\"normal\",\"start\":" << number(start)
              << ",\"end\":" << number(end) << "}]\n";
    return 0;
}
