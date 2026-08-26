#include "metrics/aggregate.hpp"
#include "metrics/bins.hpp"
#include "metrics/goertzel.hpp"
#include "metrics/reconstruct.hpp"
#include "metrics/window.hpp"
#include "metrics/types.hpp"

#include <cmath>
#include <cstddef>
#include <numeric>
#include <optional>
#include <vector>

namespace tone {

namespace {

std::vector<double> build_frame(const std::vector<std::optional<double>>& samples, std::size_t start,
                                std::size_t frame_len, const std::string& detrend) {
  std::vector<double> numeric;
  numeric.reserve(frame_len);
  for (std::size_t i = 0; i < frame_len; ++i) {
    const auto& sample = samples[start + i];
    if (sample.has_value()) {
      numeric.push_back(*sample);
    }
  }
  const double mean = numeric.empty()
                          ? 0.0
                          : std::accumulate(numeric.begin(), numeric.end(), 0.0) /
                                static_cast<double>(numeric.size());

  std::vector<double> frame(frame_len, 0.0);
  for (std::size_t i = 0; i < frame_len; ++i) {
    const auto& sample = samples[start + i];
    if (!sample.has_value()) {
      frame[i] = 0.0;
    } else if (detrend == "mean") {
      frame[i] = *sample - mean;
    } else {
      frame[i] = *sample;
    }
  }
  return frame;
}

bool frame_has_null(const std::vector<std::optional<double>>& samples, std::size_t start,
                    std::size_t frame_len) {
  for (std::size_t i = 0; i < frame_len; ++i) {
    if (!samples[start + i].has_value()) {
      return true;
    }
  }
  return false;
}

double frame_quality(const std::vector<std::optional<double>>& samples, std::size_t start,
                     std::size_t frame_len) {
  std::size_t numeric_count = 0;
  for (std::size_t i = 0; i < frame_len; ++i) {
    if (samples[start + i].has_value()) {
      ++numeric_count;
    }
  }
  return static_cast<double>(numeric_count) / static_cast<double>(frame_len);
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
  out.frame_count = 0;
  out.dropped_frame_count = 0;
  out.rejected_frame_count = 0;
  out.window_energy = coefficient_window_energy(spec.frame_len);

  std::vector<std::vector<double>> retained;
  if (spec.frame_len > 0 && spec.hop_len > 0 && out.sample_count >= spec.frame_len) {
    for (std::size_t start = 0; start + spec.frame_len <= out.sample_count; start += spec.hop_len) {
      if (spec.gap_policy == "skip_frame" && frame_has_null(timeline, start, spec.frame_len)) {
        ++out.dropped_frame_count;
        continue;
      }
      if (schema_version >= 3 &&
          frame_quality(timeline, start, spec.frame_len) < spec.min_frame_quality) {
        ++out.rejected_frame_count;
        continue;
      }
      retained.push_back(
          apply_hann(build_frame(timeline, start, spec.frame_len, spec.detrend), spec.frame_len));
      ++out.frame_count;
    }
  }

  for (const auto& band_spec : spec.bands) {
    BandResult band;
    band.name = band_spec.name;
    band.low_hz = band_spec.low_hz;
    band.high_hz = band_spec.high_hz;
    band.weight = schema_version >= 3 ? band_spec.weight : 1.0;

    const std::vector<std::size_t> bins =
        select_bins(spec.frame_len, spec.sample_rate_hz, band_spec);
    band.bin_count = bins.size();

    double raw_energy = 0.0;
    std::vector<double> peak_sums(bins.size(), 0.0);
    for (const auto& windowed : retained) {
      for (std::size_t bi = 0; bi < bins.size(); ++bi) {
        const GoertzelResult g = goertzel_bin(windowed, bins[bi]);
        const double magnitude_sq = g.real * g.real + g.imag * g.imag;
        raw_energy += band.weight * magnitude_sq;
        peak_sums[bi] += magnitude_sq;
      }
    }

    if (out.frame_count == 0 || spec.frame_len == 0 || out.window_energy <= 0.0 || bins.empty()) {
      band.energy = 0.0;
      band.peak_bin = -1;
      band.peak_hz = 0.0;
    } else {
      const double denom = static_cast<double>(out.frame_count) * static_cast<double>(spec.frame_len) *
                           static_cast<double>(spec.frame_len) * out.window_energy;
      band.energy = raw_energy / denom;

      std::size_t best_idx = 0;
      for (std::size_t bi = 1; bi < bins.size(); ++bi) {
        if (peak_sums[bi] > peak_sums[best_idx] ||
            (peak_sums[bi] == peak_sums[best_idx] && bins[bi] < bins[best_idx])) {
          best_idx = bi;
        }
      }
      band.peak_bin = static_cast<int>(bins[best_idx]);
      band.peak_hz =
          static_cast<double>(band.peak_bin) * spec.sample_rate_hz / static_cast<double>(spec.frame_len);
    }

    out.bands.push_back(band);
  }

  return out;
}

}  // namespace tone
