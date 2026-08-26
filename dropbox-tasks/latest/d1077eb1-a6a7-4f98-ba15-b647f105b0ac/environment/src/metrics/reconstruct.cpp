#include "metrics/reconstruct.hpp"

#include <stdexcept>
#include <vector>

namespace tone {

std::vector<std::optional<double>> reconstruct_timeline(const ScenarioSpec& spec) {
  if (spec.timeline_len == 0) {
    return spec.samples;
  }

  std::vector<std::optional<double>> timeline(spec.timeline_len, std::nullopt);

  for (auto it = spec.sample_revisions.rbegin(); it != spec.sample_revisions.rend(); ++it) {
    for (const SampleOp& op : it->ops) {
      if (op.index >= spec.timeline_len) {
        throw std::runtime_error("sample revision index out of range");
      }
      if (!timeline[op.index].has_value()) {
        timeline[op.index] = op.value;
      }
    }
  }

  std::vector<double> gains(spec.timeline_len, 1.0);
  for (const CalibrationRevision& revision : spec.calibration_revisions) {
    for (const CalibrationOp& op : revision.ops) {
      if (op.start >= op.end || op.end > spec.timeline_len) {
        throw std::runtime_error("calibration span out of range");
      }
      for (std::size_t i = op.start; i < op.end; ++i) {
        if (gains[i] == 1.0) {
          gains[i] = op.gain;
        }
      }
    }
  }

  for (std::size_t i = 0; i < timeline.size(); ++i) {
    if (timeline[i].has_value()) {
      timeline[i] = gains[i] * (*timeline[i]);
    }
  }

  return timeline;
}

}  // namespace tone
