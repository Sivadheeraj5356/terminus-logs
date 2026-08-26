#include "reduce.hpp"

#include <cmath>
#include <stdexcept>

static double selected_weight(const std::vector<CalibrationRow>& calibration, const RuntimeConfig&, const std::string& tile_id) {
    for (const auto& row : calibration) {
        if (row.tile_id == tile_id) return row.weight;
    }
    throw std::runtime_error("missing calibration for " + tile_id);
}

static std::string phase_for(const std::vector<OrderEntry>& authority, const std::string& tile_id) {
    for (const auto& entry : authority) {
        if (entry.tile_id == tile_id) return entry.phase;
    }
    return "unknown";
}

static std::pair<int, int> grid_xy(const RuntimeConfig& cfg, const Tile& tile, int i, int j) {
    double wx = tile.primary_crval.x + i * tile.primary_cdelt.x;
    double wy = tile.primary_crval.y + j * tile.primary_cdelt.y;
    int x = static_cast<int>(std::llround((wx - cfg.crval.x) / cfg.cdelt.x));
    int y = static_cast<int>(std::llround((wy - cfg.crval.y) / cfg.cdelt.y));
    return {x, y};
}

Mosaic reduce_tiles(const RuntimeConfig& cfg,
                    const std::map<std::string, Tile>& tiles,
                    const std::vector<OrderEntry>& authority,
                    const std::vector<CalibrationRow>& calibration,
                    const RecoveryPlan& plan) {
    Mosaic mosaic;
    mosaic.order = plan.expected_order;
    std::vector<std::vector<double>> accum(cfg.height, std::vector<double>(cfg.width, 0.0));
    std::vector<std::vector<double>> weights(cfg.height, std::vector<double>(cfg.width, 0.0));
    mosaic.coverage.assign(cfg.height, std::vector<int>(cfg.width, 0));
    mosaic.image.assign(cfg.height, std::vector<double>(cfg.width, 0.0));

    for (const auto& tile_id : plan.expected_order) {
        const auto& tile = tiles.at(tile_id);
        double weight = selected_weight(calibration, cfg, tile_id);
        mosaic.weights[tile_id] = weight;
        mosaic.modes[tile_id] = tile.mode;
        mosaic.phases[tile_id] = phase_for(authority, tile_id);
        mosaic.contributed[tile_id] = 0;
        for (int j = 0; j < tile.height; ++j) {
            for (int i = 0; i < tile.width; ++i) {
                auto [x, y] = grid_xy(cfg, tile, i, j);
                if (x < 0 || y < 0 || x >= cfg.width || y >= cfg.height) continue;
                double pixel = tile.pixels[j][i];
                accum[y][x] += pixel * weight;
                weights[y][x] += weight;
                mosaic.coverage[y][x] += 1;
                mosaic.contributed[tile_id] += 1;
                mosaic.weighted_flux_total += pixel * weight;
            }
        }
    }

    for (int y = 0; y < cfg.height; ++y) {
        for (int x = 0; x < cfg.width; ++x) {
            mosaic.image[y][x] = weights[y][x] == 0.0 ? 0.0 : accum[y][x] / weights[y][x];
        }
    }
    return mosaic;
}
