#include "audit.hpp"
#include "io.hpp"
#include "publish.hpp"
#include "reduce.hpp"
#include "replay.hpp"

#include <iostream>
#include <map>
#include <stdexcept>

static int recover(const std::string& data_dir, const std::string& work_dir) {
    RuntimeConfig cfg = parse_run_config(data_dir + "/run-config.tsv");
    auto authority = parse_order(data_dir + "/tile-order-authority.tsv");
    auto plan = build_recovery_plan(data_dir, work_dir, authority);
    auto calibration = parse_calibration(data_dir + "/calibration.tsv");
    std::map<std::string, Tile> tiles;
    for (const auto& tile_id : plan.expected_order) {
        tiles[tile_id] = parse_tile(data_dir + "/tiles/" + tile_id + ".tile");
    }
    auto mosaic = reduce_tiles(cfg, tiles, authority, calibration, plan);
    auto samples = parse_samples(data_dir + "/world-samples.tsv");
    auto thresholds = parse_thresholds(data_dir + "/contour-thresholds.tsv");
    publish_all(work_dir, cfg, plan, mosaic, samples, thresholds);
    std::cout << "recovered " << mosaic.order.size() << " tiles into " << work_dir << "\n";
    return 0;
}

int main(int argc, char** argv) {
    try {
        if (argc == 4 && std::string(argv[1]) == "recover") return recover(argv[2], argv[3]);
        if (argc == 3 && std::string(argv[1]) == "audit") return audit_fits(argv[2]);
        if (argc == 4 && std::string(argv[1]) == "render") return render_from_fits(argv[2], argv[3]);
        if (argc == 5 && std::string(argv[1]) == "sample") return sample_fits(argv[2], argv[3], argv[4]);
        std::cerr << "usage: mosaicctl recover <data-dir> <work-dir> | audit <mosaic.fits> | render <mosaic.fits> <out.svg> | sample <mosaic.fits> <world_x> <world_y>\n";
        return 64;
    } catch (const std::exception& exc) {
        std::cerr << exc.what() << "\n";
        return 1;
    }
}
