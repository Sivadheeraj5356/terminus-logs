#pragma once

#include <map>
#include <string>
#include <vector>

using Lines = std::vector<std::string>;

struct Vec2 {
    double x = 0.0;
    double y = 0.0;
};

struct RuntimeConfig {
    std::string profile;
    std::string epoch;
    int width = 0;
    int height = 0;
    Vec2 crval;
    Vec2 cdelt;
};

struct Tile {
    std::string id;
    std::string mode;
    int width = 0;
    int height = 0;
    Vec2 primary_crval;
    Vec2 primary_cdelt;
    Vec2 alt_crval;
    Vec2 alt_cdelt;
    std::vector<std::vector<double>> pixels;
};

struct OrderEntry {
    int index = 0;
    std::string tile_id;
    std::string phase;
};

struct CalibrationRow {
    std::string tile_id;
    std::string profile;
    std::string epoch;
    double weight = 0.0;
};

struct SamplePoint {
    std::string id;
    double world_x = 0.0;
    double world_y = 0.0;
};

struct JournalRecord {
    int seq = 0;
    std::string event;
    std::string tile_id;
    std::string generation;
    std::string artifact;
};

struct RecoveryPlan {
    std::vector<std::string> expected_order;
    std::vector<std::string> committed_prefix;
    std::vector<std::string> resumed_tiles;
    std::vector<std::string> rolled_back;
    std::string source;
};

struct Mosaic {
    std::vector<std::string> order;
    std::vector<std::vector<double>> image;
    std::vector<std::vector<int>> coverage;
    std::map<std::string, int> contributed;
    std::map<std::string, double> weights;
    std::map<std::string, std::string> modes;
    std::map<std::string, std::string> phases;
    double weighted_flux_total = 0.0;
};
