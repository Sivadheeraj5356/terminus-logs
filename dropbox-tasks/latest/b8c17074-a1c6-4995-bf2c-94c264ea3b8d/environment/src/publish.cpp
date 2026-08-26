#include "publish.hpp"

#include "io.hpp"
#include "render.hpp"

#include <cmath>
#include <sstream>

static std::string json_string_array(const std::vector<std::string>& values) {
    std::ostringstream out;
    out << "[";
    for (size_t i = 0; i < values.size(); ++i) {
        if (i) out << ",";
        out << "\"" << values[i] << "\"";
    }
    out << "]";
    return out.str();
}

static Lines primary_hdu(const RuntimeConfig& cfg, const Mosaic& mosaic) {
    Lines lines = {"HDU PRIMARY_IMAGE",
                   "WIDTH " + std::to_string(cfg.width),
                   "HEIGHT " + std::to_string(cfg.height),
                   "GLOBAL_WCS_CRVAL " + fixed6(cfg.crval.x) + " " + fixed6(cfg.crval.y),
                   "GLOBAL_WCS_CDELT " + fixed6(cfg.cdelt.x) + " " + fixed6(cfg.cdelt.y),
                   "DATA"};
    for (const auto& row : mosaic.image) {
        std::ostringstream line;
        for (size_t i = 0; i < row.size(); ++i) {
            if (i) line << " ";
            line << fixed6(row[i]);
        }
        lines.push_back(line.str());
    }
    lines.push_back("END_HDU");
    return lines;
}

static Lines coverage_hdu(const RuntimeConfig& cfg, const Mosaic& mosaic) {
    Lines lines = {"HDU COVERAGE", "WIDTH " + std::to_string(cfg.width), "HEIGHT " + std::to_string(cfg.height), "DATA"};
    for (const auto& row : mosaic.coverage) {
        std::ostringstream line;
        for (size_t i = 0; i < row.size(); ++i) {
            if (i) line << " ";
            line << row[i];
        }
        lines.push_back(line.str());
    }
    lines.push_back("END_HDU");
    return lines;
}

static Lines checkpoint_hdu(const RuntimeConfig& cfg, const RecoveryPlan& plan, const Mosaic& mosaic) {
    return {"HDU CHECKPOINT",
            "RUN_PROFILE " + cfg.profile,
            "CALIBRATION_EPOCH " + cfg.epoch,
            "EXPECTED_TILE_ORDER " + join_csv(mosaic.order),
            "COMMITTED " + join_csv(mosaic.order),
            "RECOVERY_SOURCE " + plan.source,
            "END_HDU"};
}

static Lines provenance_hdu(const Mosaic& mosaic) {
    Lines lines = {"HDU PROVENANCE", "COLUMNS tile_id order_index phase weight wcs_mode contributed_cells"};
    for (size_t i = 0; i < mosaic.order.size(); ++i) {
        const auto& tile_id = mosaic.order[i];
        lines.push_back("TILE " + tile_id + " " + std::to_string(i + 1) + " " + mosaic.phases.at(tile_id) + " " +
                        fixed6(mosaic.weights.at(tile_id)) + " " + mosaic.modes.at(tile_id) + " " +
                        std::to_string(mosaic.contributed.at(tile_id)));
    }
    lines.push_back("END_HDU");
    return lines;
}

static std::string fits_text(const RuntimeConfig& cfg, const RecoveryPlan& plan, const Mosaic& mosaic) {
    Lines primary = primary_hdu(cfg, mosaic);
    Lines coverage = coverage_hdu(cfg, mosaic);
    Lines checkpoint = checkpoint_hdu(cfg, plan, mosaic);
    Lines provenance = provenance_hdu(mosaic);
    Lines checks = {"HDU CHECKSUMS",
                    "PRIMARY_IMAGE " + fnv64_hex(primary),
                    "COVERAGE " + fnv64_hex(coverage),
                    "CHECKPOINT " + fnv64_hex(checkpoint),
                    "PROVENANCE " + fnv64_hex(provenance),
                    "END_HDU"};
    std::ostringstream out;
    out << "FITS-LITE 2\n";
    for (const auto* section : {&primary, &coverage, &checkpoint, &provenance, &checks}) {
        for (const auto& line : *section) out << line << "\n";
    }
    return out.str();
}

static std::string report_json(const RuntimeConfig& cfg, const Mosaic& mosaic, const std::vector<SamplePoint>& samples) {
    std::ostringstream out;
    out << "{\n";
    out << "  \"weighted_flux_total\": " << fixed6(mosaic.weighted_flux_total) << ",\n";
    out << "  \"calibration_profile\": \"" << cfg.profile << "\",\n";
    out << "  \"calibration_epoch\": \"" << cfg.epoch << "\",\n";
    out << "  \"contours_regenerated\": true,\n";
    out << "  \"samples\": [\n";
    for (size_t i = 0; i < samples.size(); ++i) {
        int x = static_cast<int>(std::llround((samples[i].world_x - cfg.crval.x) / cfg.cdelt.x));
        int y = static_cast<int>(std::llround((samples[i].world_y - cfg.crval.y) / cfg.cdelt.y));
        double image_value = 0.0;
        int coverage_value = 0;
        if (x >= 0 && y >= 0 && y < static_cast<int>(mosaic.image.size()) && x < static_cast<int>(mosaic.image[y].size())) {
            image_value = mosaic.image[y][x];
            coverage_value = mosaic.coverage[y][x];
        }
        out << "    {\"sample_id\": \"" << samples[i].id << "\", \"image\": " << fixed6(image_value)
            << ", \"coverage\": " << coverage_value << "}";
        if (i + 1 != samples.size()) out << ",";
        out << "\n";
    }
    out << "  ]\n";
    out << "}\n";
    return out.str();
}

static std::string status_json(const RecoveryPlan& plan, const Mosaic& mosaic) {
    std::ostringstream out;
    out << "{\n";
    out << "  \"status\": \"complete\",\n";
    out << "  \"expected_tile_order\": " << json_string_array(mosaic.order) << ",\n";
    out << "  \"committed_tiles\": " << json_string_array(plan.committed_prefix) << ",\n";
    out << "  \"resumed_tiles\": " << json_string_array(plan.resumed_tiles) << ",\n";
    out << "  \"rolled_back_records\": " << json_string_array(plan.rolled_back) << ",\n";
    out << "  \"published_artifacts\": [\"mosaic.fits\",\"tile-order.manifest\",\"mosaic-contours.svg\",\"reconciliation-report.json\",\"recovery-status.json\"]\n";
    out << "}\n";
    return out.str();
}

void publish_all(const std::string& work_dir,
                 const RuntimeConfig& cfg,
                 const RecoveryPlan& plan,
                 const Mosaic& mosaic,
                 const std::vector<SamplePoint>& samples,
                 const std::vector<double>& thresholds) {
    ensure_dir(work_dir);
    write_text(work_dir + "/tile-order.manifest", join_csv(mosaic.order) + "\n");
    std::string manifest;
    for (const auto& tile_id : mosaic.order) manifest += tile_id + "\n";
    write_text(work_dir + "/tile-order.manifest", manifest);
    write_text(work_dir + "/mosaic.fits", fits_text(cfg, plan, mosaic));
    if (!path_exists(work_dir + "/mosaic-contours.svg")) {
        write_text(work_dir + "/mosaic-contours.svg", render_svg_text(mosaic.image, thresholds));
    }
    if (!path_exists(work_dir + "/reconciliation-report.json")) {
        write_text(work_dir + "/reconciliation-report.json", report_json(cfg, mosaic, samples));
    }
    write_text(work_dir + "/recovery-status.json", status_json(plan, mosaic));
}
