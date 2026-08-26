function clamp(value, minimum, maximum) {
  return Math.min(maximum, Math.max(minimum, value));
}

function boundaryAt(config, x, y) {
  if (y === 0) return config.boundaries.top;
  if (x === 0) return config.boundaries.left;
  if (x === config.width - 1) return config.boundaries.right;
  if (y === config.height - 1) return config.boundaries.bottom;
  return null;
}

function materialAt(config, x, y) {
  return (
    Math.floor(x / config.block_width)
    + Math.floor(y / config.block_height)
    + config.material_offset
  ) % config.materials.length;
}

function initialFields(config) {
  const temperature = Array.from({ length: config.height }, () => Array(config.width).fill(0));
  const cure = Array.from({ length: config.height }, () => Array(config.width).fill(0));
  for (let y = 0; y < config.height; y += 1) {
    for (let x = 0; x < config.width; x += 1) {
      const boundary = boundaryAt(config, x, y);
      if (boundary !== null) {
        temperature[y][x] = boundary.temperature_milli_c;
        cure[y][x] = boundary.cure_ppm;
        continue;
      }
      let value = config.base_temperature_milli_c;
      for (const hotspot of config.hotspots) {
        const distance = Math.abs(x - hotspot.x) + Math.abs(y - hotspot.y);
        value += Math.max(0, hotspot.peak_milli_c - hotspot.decay_per_cell_milli_c * distance);
      }
      temperature[y][x] = clamp(value, config.temperature_floor_milli_c, config.temperature_ceiling_milli_c);
      cure[y][x] = config.base_cure_ppm;
    }
  }
  return { temperature, cure };
}

function pulseHeat(config, step, x, y) {
  let total = 0;
  for (const pulse of config.heater_pulses) {
    if (step < pulse.start_step || step > pulse.end_step) continue;
    const distance = Math.abs(x - pulse.x) + Math.abs(y - pulse.y);
    total += Math.max(0, pulse.strength_milli_c - pulse.decay_per_cell_milli_c * distance);
  }
  return total;
}

function fieldStats(config, temperature, cure) {
  let totalTemperature = 0;
  let totalCure = 0;
  let hotCellCount = 0;
  let fullCureCellCount = 0;
  for (let y = 0; y < config.height; y += 1) {
    for (let x = 0; x < config.width; x += 1) {
      const temperatureValue = temperature[y][x];
      const cureValue = cure[y][x];
      totalTemperature += temperatureValue;
      totalCure += cureValue;
      if (temperatureValue >= config.activation_temperature_milli_c) hotCellCount += 1;
      if (cureValue >= config.full_cure_ppm) fullCureCellCount += 1;
    }
  }
  return {
    total_temperature_milli_c: totalTemperature,
    total_cure_ppm: totalCure,
    hot_cell_count: hotCellCount,
    full_cure_cell_count: fullCureCellCount,
  };
}

function simulate(config) {
  let { temperature, cure } = initialFields(config);
  const checkpointSet = new Set(config.checkpoint_steps);
  const checkpointTotals = { '0': fieldStats(config, temperature, cure) };
  const events = [];

  for (let step = 1; step <= config.steps; step += 1) {
    const nextTemperature = temperature.map((row) => row.slice());
    for (let y = 0; y < config.height; y += 1) {
      for (let x = 0; x < config.width; x += 1) {
        const boundary = boundaryAt(config, x, y);
        if (boundary !== null) {
          nextTemperature[y][x] = boundary.temperature_milli_c;
          continue;
        }
        const materialIndex = materialAt(config, x, y);
        const material = config.materials[materialIndex];
        const numerator = (
          material.retain * temperature[y][x]
          + material.horizontal * (nextTemperature[y][x - 1] + temperature[y][x + 1])
          + material.vertical * (nextTemperature[y - 1][x] + temperature[y + 1][x])
          + material.diagonal * (
            temperature[y - 1][x - 1]
            + temperature[y - 1][x + 1]
            + temperature[y + 1][x - 1]
            + temperature[y + 1][x + 1]
          )
        );
        const denominator = material.retain + 2 * material.horizontal + 2 * material.vertical + 4 * material.diagonal;
        const mixed = Math.floor(numerator / denominator);
        const cureTerm = Math.floor(
          (cure[y][x] - config.base_cure_ppm) * material.heater_gain / 1000000,
        );
        nextTemperature[y][x] = clamp(
          mixed + pulseHeat(config, step, x, y) + cureTerm,
          config.temperature_floor_milli_c,
          config.temperature_ceiling_milli_c,
        );
      }
    }

    const nextCure = cure.map((row) => row.slice());
    for (let y = 0; y < config.height; y += 1) {
      for (let x = 0; x < config.width; x += 1) {
        const boundary = boundaryAt(config, x, y);
        if (boundary !== null) {
          nextCure[y][x] = boundary.cure_ppm;
          continue;
        }
        const materialIndex = materialAt(config, x, y);
        const material = config.materials[materialIndex];
        let delta;
        if (temperature[y][x] >= config.activation_temperature_milli_c) {
          delta = material.cure_rate_ppm + Math.floor(
            (temperature[y][x] - config.activation_temperature_milli_c) / 2500,
          );
        } else {
          delta = -material.cool_rate_ppm;
        }
        nextCure[y][x] = clamp(cure[y][x] + delta, 0, 1000000);
        if (cure[y][x] < config.full_cure_ppm && nextCure[y][x] >= config.full_cure_ppm) {
          events.push({
            step,
            x,
            y,
            material: materialIndex,
            temperature_milli_c: nextTemperature[y][x],
            cure_ppm: nextCure[y][x],
          });
        }
      }
    }
    temperature = nextTemperature;
    cure = nextCure;
    if (checkpointSet.has(step)) checkpointTotals[String(step)] = fieldStats(config, temperature, cure);
  }

  return { temperature, cure, events, checkpointTotals };
}

module.exports = { boundaryAt, fieldStats, initialFields, materialAt, simulate };
