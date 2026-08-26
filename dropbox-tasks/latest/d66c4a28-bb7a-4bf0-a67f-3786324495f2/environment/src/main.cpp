#include <iostream>
#include <string>
#include "spec_loader.hpp"
#include "derive.hpp"
#include "manifest.hpp"

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cerr << "Usage: derive --sources <dir> --csv <manifest_inputs.csv> "
                     "--spec <asset_processing_spec.md> --out <out_dir>\n";
        return 2;
    }
    // TODO: parse args, load spec, read CSV, process each source, write manifest.
    return 2;
}
