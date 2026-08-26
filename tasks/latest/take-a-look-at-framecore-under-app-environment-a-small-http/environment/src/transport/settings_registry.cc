#include "framecore/transport/settings_registry.h"

namespace framecore {

void SettingsRegistry::Apply(uint16_t id, uint32_t value) { values_[id] = value; }

bool SettingsRegistry::Get(uint16_t id, uint32_t* out) const {
  auto it = values_.find(id);
  if (it == values_.end()) {
    return false;
  }
  *out = it->second;
  return true;
}

}
