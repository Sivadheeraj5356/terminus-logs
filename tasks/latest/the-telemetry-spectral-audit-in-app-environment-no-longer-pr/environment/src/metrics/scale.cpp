#include "metrics/aggregate.hpp"
#include "metrics/bins.hpp"
#include "metrics/goertzel.hpp"
#include "metrics/reconstruct.hpp"
#include "metrics/window.hpp"
#include "metrics/types.hpp"

#include <cmath>
#include <cstddef>
#include <optional>
#include <vector>

namespace tone {

namespace {

std::vector<double> flatten_numeric(const std::vector<std::optional<double>>& samples) {
  std::vector<double> out;
  out.reserve(samples.size());
  for (const auto& sample : samples) {
    if (sample.has_value()) {
      out.push_back(*sample);
    }
  }
  return out;
}

double scale_band_power(double raw_power, std::size_t n, double window_energy) {
  if (n == 0 || window_energy <= 0.0) {
    return 0.0;
  }
  const double denom = static_cast<double>(n) * window_energy;
  return raw_power / denom;
}

}  // namespace

ScenarioResult evaluate_scenario(const ScenarioSpec& spec, int schema_version) {
  ScenarioResult out;
  out.id = spec.id;

  const std::vector<std::optional<double>> timeline =
      spec.timeline_len > 0 ? reconstruct_timeline(spec) : spec.samples;

  out.sample_count = timeline.size();
  out.valid_sample_count = 0;
  for (const auto& sample : timeline) {
    if (sample.has_value()) {
      ++out.valid_sample_count;
    }
  }
  out.frame_len = spec.frame_len;
  out.hop_len = spec.hop_len;
  out.frame_count = 1;
  out.dropped_frame_count = 0;
  out.rejected_frame_count = 0;
  out.window_energy = coefficient_window_energy(spec.frame_len);

  const std::vector<double> numeric = flatten_numeric(timeline);
  const std::vector<double> windowed = apply_hann(numeric, numeric.size());

  for (const auto& band_spec : spec.bands) {
    BandResult band;
    band.name = band_spec.name;
    band.low_hz = band_spec.low_hz;
    band.high_hz = band_spec.high_hz;
    band.weight = schema_version >= 3 ? band_spec.weight : 1.0;

    const std::vector<std::size_t> bins =
        select_bins(out.sample_count > 0 ? out.sample_count : spec.frame_len, spec.sample_rate_hz,
                    band_spec);
    band.bin_count = bins.size();

    const double raw = aggregate_magnitude_sq(windowed, bins);
    band.energy = scale_band_power(raw, numeric.size(), out.window_energy);
    band.peak_bin = bins.empty() ? -1 : static_cast<int>(bins.front());
    band.peak_hz = band.peak_bin < 0
                       ? 0.0
                       : static_cast<double>(band.peak_bin) * spec.sample_rate_hz /
                             static_cast<double>(out.sample_count > 0 ? out.sample_count : spec.frame_len);

    out.bands.push_back(band);
  }

  return out;
}

}  // namespace tone
