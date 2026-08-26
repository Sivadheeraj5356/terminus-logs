#pragma once

#include <cstddef>
#include <cstdint>
#include <map>

namespace framecore {

class SettingsRegistry {
 public:
  void Apply(uint16_t id, uint32_t value);
  bool Get(uint16_t id, uint32_t* out) const;
  size_t size() const { return values_.size(); }

 private:
  std::map<uint16_t, uint32_t> values_;
};

}
