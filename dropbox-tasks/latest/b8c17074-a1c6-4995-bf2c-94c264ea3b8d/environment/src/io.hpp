#pragma once

#include "types.hpp"

#include <map>
#include <string>
#include <vector>

std::string trim(const std::string& s);
std::vector<std::string> split_ws(const std::string& s);
std::vector<std::string> split_tab(const std::string& s);
Lines read_lines(const std::string& path);
void write_text(const std::string& path, const std::string& text);
bool path_exists(const std::string& path);
void ensure_dir(const std::string& path);

RuntimeConfig parse_run_config(const std::string& path);
std::vector<OrderEntry> parse_order(const std::string& path);
std::vector<CalibrationRow> parse_calibration(const std::string& path);
std::vector<SamplePoint> parse_samples(const std::string& path);
std::vector<double> parse_thresholds(const std::string& path);
std::vector<JournalRecord> parse_journal(const std::string& path);
std::vector<std::string> read_manifest(const std::string& path);
Tile parse_tile(const std::string& path);

std::map<std::string, Lines> parse_hdus(const Lines& lines);
std::vector<std::vector<double>> parse_primary_image(const std::map<std::string, Lines>& hdus);
std::map<std::string, std::string> hdu_key_values(const Lines& hdu);
std::string fnv64_hex(const Lines& lines);
std::string join_csv(const std::vector<std::string>& values);
std::string fixed6(double value);
