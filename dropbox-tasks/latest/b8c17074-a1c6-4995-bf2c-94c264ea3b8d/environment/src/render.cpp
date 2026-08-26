#include "render.hpp"

#include "io.hpp"

#include <sstream>

std::string render_svg_text(const std::vector<std::vector<double>>& image, const std::vector<double>& thresholds) {
    int height = static_cast<int>(image.size());
    int width = height == 0 ? 0 : static_cast<int>(image[0].size());
    std::ostringstream out;
    out << "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"" << (width * 100) << "\" height=\"" << (height * 100)
        << "\" viewBox=\"0 0 " << width << " " << height << "\" data-source=\"mosaic.fits\">\n";
    for (double level : thresholds) {
        std::vector<std::string> cells;
        std::ostringstream path;
        for (int y = 0; y < height; ++y) {
            for (int x = 0; x < width; ++x) {
                if (image[y][x] + 1e-12 >= level) {
                    cells.push_back(std::to_string(x) + "," + std::to_string(y));
                    path << "M" << x << "," << y << "h1v1h-1z";
                }
            }
        }
        out << "  <path id=\"level-" << static_cast<int>(level) << "\" data-threshold=\"" << fixed6(level)
            << "\" data-cells=\"";
        for (size_t i = 0; i < cells.size(); ++i) {
            if (i) out << ";";
            out << cells[i];
        }
        out << "\" d=\"" << path.str() << "\"/>\n";
    }
    out << "</svg>\n";
    return out.str();
}
