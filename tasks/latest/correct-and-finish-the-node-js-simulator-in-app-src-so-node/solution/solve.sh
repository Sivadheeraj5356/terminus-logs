#!/bin/bash
set -euo pipefail

python3 - <<'PY'
from pathlib import Path

Path("/app/src/config.js").write_text(r'''const fs = require('fs');
const path = require('path');

function fail(message) {
  throw new Error(message);
}

function integer(value, name, minimum, maximum) {
  if (!Number.isSafeInteger(value) || value < minimum || value > maximum) {
    fail(`invalid ${name}`);
  }
}

function parseArgs(argv) {
  let configPath = null;
  let outDir = null;
  for (let index = 0; index < argv.length; index += 1) {
    const flag = argv[index];
    if (flag !== '--config' && flag !== '--out') fail(`unknown argument ${flag}`);
    if (index + 1 >= argv.length) fail(`missing value for ${flag}`);
    const value = argv[index + 1];
    index += 1;
    if (flag === '--config') {
      if (configPath !== null) fail('duplicate --config');
      configPath = value;
    } else {
      if (outDir !== null) fail('duplicate --out');
      outDir = value;
    }
  }
  if (configPath === null || outDir === null) fail('both --config and --out are required');
  if (!path.isAbsolute(configPath) || !path.isAbsolute(outDir)) fail('paths must be absolute');
  return { configPath, outDir };
}

function validateConfig(config) {
  if (config === null || Array.isArray(config) || typeof config !== 'object') fail('config root must be an object');
  if (typeof config.scenario !== 'string' || config.scenario.trim() === '') fail('invalid scenario');
  integer(config.width, 'width', 5, 80);
  integer(config.height, 'height', 5, 80);
  integer(config.steps, 'steps', 1, 200);
  integer(config.block_width, 'block_width', 1, Number.MAX_SAFE_INTEGER);
  integer(config.block_height, 'block_height', 1, Number.MAX_SAFE_INTEGER);
  integer(config.material_offset, 'material_offset', 0, Number.MAX_SAFE_INTEGER);
  integer(config.temperature_floor_milli_c, 'temperature_floor_milli_c', Number.MIN_SAFE_INTEGER, Number.MAX_SAFE_INTEGER);
  integer(config.temperature_ceiling_milli_c, 'temperature_ceiling_milli_c', Number.MIN_SAFE_INTEGER, Number.MAX_SAFE_INTEGER);
  if (config.temperature_floor_milli_c >= config.temperature_ceiling_milli_c) fail('invalid temperature range');
  integer(config.base_temperature_milli_c, 'base_temperature_milli_c', Number.MIN_SAFE_INTEGER, Number.MAX_SAFE_INTEGER);
  integer(config.activation_temperature_milli_c, 'activation_temperature_milli_c', config.temperature_floor_milli_c, config.temperature_ceiling_milli_c);
  integer(config.base_cure_ppm, 'base_cure_ppm', 0, 1000000);
  integer(config.full_cure_ppm, 'full_cure_ppm', 1, 1000000);
  integer(config.stress_alert_ppm, 'stress_alert_ppm', 1, 1000000);

  if (!Array.isArray(config.checkpoint_steps) || config.checkpoint_steps.length < 2) fail('invalid checkpoint_steps');
  config.checkpoint_steps.forEach((step, index) => {
    integer(step, `checkpoint_steps[${index}]`, 0, config.steps);
    if (index > 0 && step <= config.checkpoint_steps[index - 1]) fail('checkpoint_steps must be strictly increasing');
  });
  if (config.checkpoint_steps[0] !== 0 || config.checkpoint_steps.at(-1) !== config.steps) fail('checkpoint_steps must span the run');

  if (!Array.isArray(config.materials) || config.materials.length < 2 || config.materials.length > 5) fail('invalid materials');
  config.materials.forEach((material, index) => {
    if (material === null || Array.isArray(material) || typeof material !== 'object') fail(`invalid material ${index}`);
    for (const key of ['retain', 'horizontal', 'vertical', 'diagonal', 'heater_gain', 'stress_gain', 'cure_stress_gain', 'stress_relief_ppm']) {
      integer(material[key], `materials[${index}].${key}`, 0, Number.MAX_SAFE_INTEGER);
    }
    integer(material.stress_retain_ppm, `materials[${index}].stress_retain_ppm`, 0, 1000000);
    integer(material.cure_rate_ppm, `materials[${index}].cure_rate_ppm`, 1, Number.MAX_SAFE_INTEGER);
    integer(material.cool_rate_ppm, `materials[${index}].cool_rate_ppm`, 1, Number.MAX_SAFE_INTEGER);
    const denominator = (
      BigInt(material.retain)
      + 2n * BigInt(material.horizontal)
      + 2n * BigInt(material.vertical)
      + 4n * BigInt(material.diagonal)
    );
    if (denominator <= 0n) fail(`material ${index} has zero stencil weight`);
  });

  if (config.boundaries === null || Array.isArray(config.boundaries) || typeof config.boundaries !== 'object') fail('invalid boundaries');
  for (const side of ['left', 'right', 'top', 'bottom']) {
    const boundary = config.boundaries[side];
    if (boundary === null || Array.isArray(boundary) || typeof boundary !== 'object') fail(`invalid ${side} boundary`);
    integer(boundary.temperature_milli_c, `${side}.temperature_milli_c`, config.temperature_floor_milli_c, config.temperature_ceiling_milli_c);
    integer(boundary.cure_ppm, `${side}.cure_ppm`, 0, 1000000);
  }

  if (!Array.isArray(config.hotspots)) fail('invalid hotspots');
  config.hotspots.forEach((hotspot, index) => {
    if (hotspot === null || Array.isArray(hotspot) || typeof hotspot !== 'object') fail(`invalid hotspot ${index}`);
    integer(hotspot.x, `hotspots[${index}].x`, 0, config.width - 1);
    integer(hotspot.y, `hotspots[${index}].y`, 0, config.height - 1);
    integer(hotspot.peak_milli_c, `hotspots[${index}].peak_milli_c`, 0, Number.MAX_SAFE_INTEGER);
    integer(hotspot.decay_per_cell_milli_c, `hotspots[${index}].decay_per_cell_milli_c`, 0, Number.MAX_SAFE_INTEGER);
  });

  if (!Array.isArray(config.heater_pulses)) fail('invalid heater_pulses');
  config.heater_pulses.forEach((pulse, index) => {
    if (pulse === null || Array.isArray(pulse) || typeof pulse !== 'object') fail(`invalid heater_pulse ${index}`);
    integer(pulse.start_step, `heater_pulses[${index}].start_step`, 1, config.steps);
    integer(pulse.end_step, `heater_pulses[${index}].end_step`, pulse.start_step, config.steps);
    integer(pulse.x, `heater_pulses[${index}].x`, 0, config.width - 1);
    integer(pulse.y, `heater_pulses[${index}].y`, 0, config.height - 1);
    integer(pulse.strength_milli_c, `heater_pulses[${index}].strength_milli_c`, 0, Number.MAX_SAFE_INTEGER);
    integer(pulse.decay_per_cell_milli_c, `heater_pulses[${index}].decay_per_cell_milli_c`, 0, Number.MAX_SAFE_INTEGER);
  });

  if (!Array.isArray(config.relief_windows)) fail('invalid relief_windows');
  config.relief_windows.forEach((window, index) => {
    if (window === null || Array.isArray(window) || typeof window !== 'object') fail(`invalid relief_window ${index}`);
    integer(window.start_step, `relief_windows[${index}].start_step`, 1, config.steps);
    integer(window.end_step, `relief_windows[${index}].end_step`, window.start_step, config.steps);
    integer(window.x, `relief_windows[${index}].x`, 0, config.width - 1);
    integer(window.y, `relief_windows[${index}].y`, 0, config.height - 1);
    integer(window.radius, `relief_windows[${index}].radius`, 0, Number.MAX_SAFE_INTEGER);
    integer(window.relief_ppm, `relief_windows[${index}].relief_ppm`, 0, Number.MAX_SAFE_INTEGER);
    integer(window.falloff_ppm_per_cell, `relief_windows[${index}].falloff_ppm_per_cell`, 0, Number.MAX_SAFE_INTEGER);
  });

  if (!Array.isArray(config.sensor_points) || config.sensor_points.length < 1 || config.sensor_points.length > 8) fail('invalid sensor_points');
  const sensorNames = new Set();
  config.sensor_points.forEach((sensor, index) => {
    if (sensor === null || Array.isArray(sensor) || typeof sensor !== 'object') fail(`invalid sensor ${index}`);
    if (typeof sensor.name !== 'string' || !/^[A-Za-z0-9_-]+$/.test(sensor.name)) fail(`invalid sensor ${index} name`);
    if (sensorNames.has(sensor.name)) fail(`duplicate sensor ${sensor.name}`);
    sensorNames.add(sensor.name);
    integer(sensor.x, `sensor_points[${index}].x`, 0, config.width - 1);
    integer(sensor.y, `sensor_points[${index}].y`, 0, config.height - 1);
  });
  return config;
}

function loadConfig(configPath) {
  let parsed;
  try {
    parsed = JSON.parse(fs.readFileSync(configPath, 'utf8'));
  } catch (error) {
    fail(`cannot read config: ${error.message}`);
  }
  return validateConfig(parsed);
}

module.exports = { loadConfig, parseArgs, validateConfig };
''')

Path("/app/src/simulator.js").write_text(r'''function floorDivide(numerator, denominator) {
  let quotient = numerator / denominator;
  const remainder = numerator % denominator;
  if (remainder < 0n) quotient -= 1n;
  return quotient;
}

function clampExact(value, minimum, maximum) {
  const lower = BigInt(minimum);
  const upper = BigInt(maximum);
  if (value < lower) return minimum;
  if (value > upper) return maximum;
  return Number(value);
}

function absoluteDifference(left, right) {
  const difference = BigInt(left) - BigInt(right);
  return difference < 0n ? -difference : difference;
}

function boundaryAt(config, x, y) {
  if (x === 0) return config.boundaries.left;
  if (x === config.width - 1) return config.boundaries.right;
  if (y === 0) return config.boundaries.top;
  if (y === config.height - 1) return config.boundaries.bottom;
  return null;
}

function materialAt(config, x, y) {
  const index = (
    BigInt(Math.floor(x / config.block_width))
    + 2n * BigInt(Math.floor(y / config.block_height))
    + BigInt(config.material_offset)
  ) % BigInt(config.materials.length);
  return Number(index);
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
      let value = BigInt(config.base_temperature_milli_c);
      for (const hotspot of config.hotspots) {
        const distance = Math.abs(x - hotspot.x) + Math.abs(y - hotspot.y);
        const contribution = (
          BigInt(hotspot.peak_milli_c)
          - BigInt(hotspot.decay_per_cell_milli_c) * BigInt(distance)
        );
        if (contribution > 0n) value += contribution;
      }
      temperature[y][x] = clampExact(
        value,
        config.temperature_floor_milli_c,
        config.temperature_ceiling_milli_c,
      );
      cure[y][x] = config.base_cure_ppm;
    }
  }
  return { temperature, cure };
}

function pulseHeat(config, step, x, y) {
  let total = 0n;
  for (const pulse of config.heater_pulses) {
    if (step < pulse.start_step || step > pulse.end_step) continue;
    const distance = Math.abs(x - pulse.x) + Math.abs(y - pulse.y);
    const contribution = (
      BigInt(pulse.strength_milli_c)
      - BigInt(pulse.decay_per_cell_milli_c) * BigInt(distance)
    );
    if (contribution > 0n) total += contribution;
  }
  return total;
}

function reliefAt(config, step, x, y) {
  let total = 0n;
  for (const window of config.relief_windows) {
    if (step < window.start_step || step > window.end_step) continue;
    const distance = Math.abs(x - window.x) + Math.abs(y - window.y);
    if (distance <= window.radius) {
      const contribution = (
        BigInt(window.relief_ppm)
        - BigInt(window.falloff_ppm_per_cell) * BigInt(distance)
      );
      if (contribution > 0n) total += contribution;
    }
  }
  return total;
}

function fieldStats(config, temperature, cure, stress) {
  let totalTemperature = 0n;
  let totalCure = 0n;
  let hotCellCount = 0;
  let fullCureCellCount = 0;
  let peakStress = 0;
  let stressedCellCount = 0;
  for (let y = 0; y < config.height; y += 1) {
    for (let x = 0; x < config.width; x += 1) {
      const temperatureValue = temperature[y][x];
      const cureValue = cure[y][x];
      const stressValue = stress[y][x];
      totalTemperature += BigInt(temperatureValue);
      totalCure += BigInt(cureValue);
      if (temperatureValue >= config.activation_temperature_milli_c) hotCellCount += 1;
      if (cureValue >= config.full_cure_ppm) fullCureCellCount += 1;
      if (stressValue > peakStress) peakStress = stressValue;
      if (stressValue >= config.stress_alert_ppm) stressedCellCount += 1;
    }
  }
  return {
    total_temperature_milli_c: totalTemperature,
    total_cure_ppm: totalCure,
    hot_cell_count: hotCellCount,
    full_cure_cell_count: fullCureCellCount,
    peak_stress_ppm: peakStress,
    stressed_cell_count: stressedCellCount,
  };
}

function copyFields(temperature, cure, stress) {
  return {
    temperature: temperature.map((row) => row.slice()),
    cure: cure.map((row) => row.slice()),
    stress: stress.map((row) => row.slice()),
  };
}

function simulate(config) {
  let { temperature, cure } = initialFields(config);
  let stress = Array.from({ length: config.height }, () => Array(config.width).fill(0));
  const checkpointSet = new Set(config.checkpoint_steps);
  const checkpointTotals = { '0': fieldStats(config, temperature, cure, stress) };
  const checkpointSnapshots = { '0': copyFields(temperature, cure, stress) };
  const events = [];
  const stressEvents = [];
  const crossed = new Set();
  for (let y = 0; y < config.height; y += 1) {
    for (let x = 0; x < config.width; x += 1) {
      if (boundaryAt(config, x, y) === null && cure[y][x] >= config.full_cure_ppm) {
        crossed.add(`${x},${y}`);
      }
    }
  }
  const stressed = new Set();

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
          BigInt(material.retain) * BigInt(temperature[y][x])
          + BigInt(material.horizontal) * (
            BigInt(temperature[y][x - 1]) + BigInt(temperature[y][x + 1])
          )
          + BigInt(material.vertical) * (
            BigInt(temperature[y - 1][x]) + BigInt(temperature[y + 1][x])
          )
          + BigInt(material.diagonal) * (
            BigInt(temperature[y - 1][x - 1])
            + BigInt(temperature[y - 1][x + 1])
            + BigInt(temperature[y + 1][x - 1])
            + BigInt(temperature[y + 1][x + 1])
          )
        );
        const denominator = (
          BigInt(material.retain)
          + 2n * BigInt(material.horizontal)
          + 2n * BigInt(material.vertical)
          + 4n * BigInt(material.diagonal)
        );
        const mixed = floorDivide(numerator, denominator);
        const cureTerm = floorDivide(
          BigInt(cure[y][x] - config.base_cure_ppm) * BigInt(material.heater_gain),
          1000000n,
        );
        nextTemperature[y][x] = clampExact(
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
        if (nextTemperature[y][x] >= config.activation_temperature_milli_c) {
          delta = BigInt(material.cure_rate_ppm) + floorDivide(
            BigInt(nextTemperature[y][x]) - BigInt(config.activation_temperature_milli_c),
            2500n,
          );
        } else {
          delta = -BigInt(material.cool_rate_ppm);
        }
        nextCure[y][x] = clampExact(BigInt(cure[y][x]) + delta, 0, 1000000);
        const coordinate = `${x},${y}`;
        if (
          !crossed.has(coordinate)
          && cure[y][x] < config.full_cure_ppm
          && nextCure[y][x] >= config.full_cure_ppm
        ) {
          crossed.add(coordinate);
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

    const nextStress = stress.map((row) => row.slice());
    for (let y = 0; y < config.height; y += 1) {
      for (let x = 0; x < config.width; x += 1) {
        const boundary = boundaryAt(config, x, y);
        if (boundary !== null) {
          nextStress[y][x] = 0;
          continue;
        }
        const materialIndex = materialAt(config, x, y);
        const material = config.materials[materialIndex];
        const cureIncrease = Math.max(0, nextCure[y][x] - cure[y][x]);
        const generatedStress = floorDivide(
          absoluteDifference(nextTemperature[y][x], temperature[y][x]) * BigInt(material.stress_gain)
          + BigInt(cureIncrease) * BigInt(material.cure_stress_gain),
          1000n,
        );
        const retainedStress = floorDivide(
          BigInt(stress[y][x]) * BigInt(material.stress_retain_ppm),
          1000000n,
        );
        const nextValue = clampExact(
          retainedStress
            + generatedStress
            - BigInt(material.stress_relief_ppm)
            - reliefAt(config, step, x, y),
          0,
          1000000,
        );
        nextStress[y][x] = nextValue;
        const coordinate = `${x},${y}`;
        if (
          !stressed.has(coordinate)
          && stress[y][x] < config.stress_alert_ppm
          && nextValue >= config.stress_alert_ppm
        ) {
          stressed.add(coordinate);
          stressEvents.push({ step, x, y, material: materialIndex, stress_ppm: nextValue });
        }
      }
    }

    temperature = nextTemperature;
    cure = nextCure;
    stress = nextStress;
    if (checkpointSet.has(step)) {
      const checkpoint = String(step);
      checkpointTotals[checkpoint] = fieldStats(config, temperature, cure, stress);
      checkpointSnapshots[checkpoint] = copyFields(temperature, cure, stress);
    }
  }

  return { temperature, cure, stress, events, stressEvents, checkpointTotals, checkpointSnapshots };
}

module.exports = { boundaryAt, fieldStats, initialFields, materialAt, simulate };
''')

Path("/app/src/output.js").write_text(r'''const fs = require('fs');
const path = require('path');
const { fieldStats, materialAt } = require('./simulator');

function floorDivide(numerator, denominator) {
  let quotient = numerator / denominator;
  const remainder = numerator % denominator;
  if (remainder < 0n) quotient -= 1n;
  return quotient;
}

function absoluteDifference(left, right) {
  const difference = BigInt(left) - BigInt(right);
  return difference < 0n ? -difference : difference;
}

function stringifyExact(value, depth = 0) {
  if (typeof value === 'bigint') return value.toString();
  if (value === null || typeof value !== 'object') return JSON.stringify(value);
  const indentation = '  '.repeat(depth);
  const childIndentation = '  '.repeat(depth + 1);
  if (Array.isArray(value)) {
    if (value.length === 0) return '[]';
    const items = value.map((item) => `${childIndentation}${stringifyExact(item, depth + 1)}`);
    return `[\n${items.join(',\n')}\n${indentation}]`;
  }
  const entries = Object.entries(value);
  if (entries.length === 0) return '{}';
  const fields = entries.map(
    ([key, item]) => `${childIndentation}${JSON.stringify(key)}: ${stringifyExact(item, depth + 1)}`,
  );
  return `{\n${fields.join(',\n')}\n${indentation}}`;
}

function writeCsv(filePath, header, rows) {
  const lines = [header.join(',')];
  for (const row of rows) lines.push(row.join(','));
  fs.writeFileSync(filePath, `${lines.join('\n')}\n`);
}

function localGradient(temperature, x, y) {
  const center = temperature[y][x];
  const deltas = [];
  if (x > 0) deltas.push(absoluteDifference(center, temperature[y][x - 1]));
  if (x < temperature[0].length - 1) deltas.push(absoluteDifference(center, temperature[y][x + 1]));
  if (y > 0) deltas.push(absoluteDifference(center, temperature[y - 1][x]));
  if (y < temperature.length - 1) deltas.push(absoluteDifference(center, temperature[y + 1][x]));
  return deltas.reduce((largest, value) => (value > largest ? value : largest), 0n);
}

function roundedMean(values) {
  const total = values.reduce((sum, value) => sum + BigInt(value), 0n);
  const count = BigInt(values.length);
  return floorDivide(2n * total + count, 2n * count);
}

function writeOutputs(config, result, outDir) {
  const fieldRows = [];
  for (let y = 0; y < config.height; y += 1) {
    for (let x = 0; x < config.width; x += 1) {
      fieldRows.push([
        x,
        y,
        materialAt(config, x, y),
        result.temperature[y][x],
        result.cure[y][x],
      ]);
    }
  }
  writeCsv(
    path.join(outDir, 'field.csv'),
    ['x', 'y', 'material', 'temperature_milli_c', 'cure_ppm'],
    fieldRows,
  );

  const eventRows = result.events.map((event) => [
    event.step,
    event.x,
    event.y,
    event.material,
    event.temperature_milli_c,
    event.cure_ppm,
  ]);
  writeCsv(
    path.join(outDir, 'events.csv'),
    ['step', 'x', 'y', 'material', 'temperature_milli_c', 'cure_ppm'],
    eventRows,
  );

  const traceRows = [];
  const previousTemperatures = new Map();
  for (const checkpoint of config.checkpoint_steps) {
    const snapshot = result.checkpointSnapshots[String(checkpoint)];
    for (const sensor of config.sensor_points) {
      const currentTemperature = snapshot.temperature[sensor.y][sensor.x];
      const previousTemperature = previousTemperatures.has(sensor.name)
        ? previousTemperatures.get(sensor.name)
        : currentTemperature;
      traceRows.push([
        checkpoint,
        sensor.name,
        sensor.x,
        sensor.y,
        materialAt(config, sensor.x, sensor.y),
        currentTemperature,
        snapshot.cure[sensor.y][sensor.x],
        localGradient(snapshot.temperature, sensor.x, sensor.y),
        BigInt(currentTemperature) - BigInt(previousTemperature),
      ]);
      previousTemperatures.set(sensor.name, currentTemperature);
    }
  }
  writeCsv(
    path.join(outDir, 'trace.csv'),
    ['checkpoint', 'name', 'x', 'y', 'material', 'temperature_milli_c', 'cure_ppm', 'local_gradient_milli_c', 'temperature_delta_from_previous_checkpoint_milli_c'],
    traceRows,
  );

  const firstEventStepByMaterial = new Map();
  for (const event of result.events) {
    if (!firstEventStepByMaterial.has(event.material)) {
      firstEventStepByMaterial.set(event.material, event.step);
    }
  }
  const stressEventCountByMaterial = new Map();
  for (const event of result.stressEvents) {
    stressEventCountByMaterial.set(event.material, (stressEventCountByMaterial.get(event.material) || 0) + 1);
  }
  const materialRows = [];
  for (let materialIndex = 0; materialIndex < config.materials.length; materialIndex += 1) {
    const temperatures = [];
    const stresses = [];
    let cureTotal = 0n;
    for (let y = 0; y < config.height; y += 1) {
      for (let x = 0; x < config.width; x += 1) {
        if (materialAt(config, x, y) !== materialIndex) continue;
        temperatures.push(result.temperature[y][x]);
        stresses.push(result.stress[y][x]);
        cureTotal += BigInt(result.cure[y][x]);
      }
    }
    materialRows.push([
      materialIndex,
      temperatures.length,
      temperatures.length === 0 ? '' : roundedMean(temperatures),
      cureTotal,
      stresses.length === 0 ? 0 : Math.max(...stresses),
      stressEventCountByMaterial.get(materialIndex) || 0,
      firstEventStepByMaterial.has(materialIndex) ? firstEventStepByMaterial.get(materialIndex) : '',
    ]);
  }
  writeCsv(
    path.join(outDir, 'material_profile.csv'),
    ['material', 'cell_count', 'mean_temperature_milli_c', 'total_cure_ppm', 'peak_stress_ppm', 'stress_event_count', 'first_full_cure_step'],
    materialRows,
  );

  const stabilityRows = [];
  let previousCheckpoint = 0;
  for (const checkpoint of config.checkpoint_steps) {
    const snapshot = result.checkpointSnapshots[String(checkpoint)];
    for (let materialIndex = 0; materialIndex < config.materials.length; materialIndex += 1) {
      const stresses = [];
      for (let y = 0; y < config.height; y += 1) {
        for (let x = 0; x < config.width; x += 1) {
          if (materialAt(config, x, y) === materialIndex) stresses.push(snapshot.stress[y][x]);
        }
      }
      const newStressEvents = result.stressEvents.filter(
        (event) => event.material === materialIndex
          && event.step > previousCheckpoint
          && event.step <= checkpoint,
      ).length;
      stabilityRows.push([
        checkpoint,
        materialIndex,
        stresses.length === 0 ? 0 : Math.max(...stresses),
        stresses.length === 0 ? '' : roundedMean(stresses),
        stresses.filter((value) => value >= config.stress_alert_ppm).length,
        newStressEvents,
      ]);
    }
    previousCheckpoint = checkpoint;
  }
  writeCsv(
    path.join(outDir, 'stability.csv'),
    ['checkpoint', 'material', 'peak_stress_ppm', 'mean_stress_ppm', 'stressed_cell_count', 'new_stress_events'],
    stabilityRows,
  );

  const stats = fieldStats(config, result.temperature, result.cure, result.stress);
  const values = result.temperature.flat();
  const centerY = Math.floor(config.height / 2);
  const centerX = Math.floor(config.width / 2);
  const centerRowChecksum = result.temperature[centerY].reduce(
    (total, value, x) => total + BigInt(x + 1) * BigInt(value),
    0n,
  );
  let centerColumnChecksum = 0n;
  for (let y = 0; y < config.height; y += 1) {
    centerColumnChecksum += BigInt(y + 1) * BigInt(result.temperature[y][centerX]);
  }
  const summary = {
    scenario: config.scenario,
    width: config.width,
    height: config.height,
    steps: config.steps,
    min_temperature_milli_c: Math.min(...values),
    max_temperature_milli_c: Math.max(...values),
    mean_temperature_milli_c: roundedMean(values),
    hot_cell_count: stats.hot_cell_count,
    full_cure_cell_count: stats.full_cure_cell_count,
    peak_stress_ppm: stats.peak_stress_ppm,
    stressed_cell_count: stats.stressed_cell_count,
    total_temperature_milli_c: stats.total_temperature_milli_c,
    total_cure_ppm: stats.total_cure_ppm,
    center_row_checksum: centerRowChecksum,
    center_column_checksum: centerColumnChecksum,
    event_count: result.events.length,
    first_full_cure_step: result.events.length === 0 ? null : result.events[0].step,
    stress_event_count: result.stressEvents.length,
    first_stress_alert_step: result.stressEvents.length === 0 ? null : result.stressEvents[0].step,
    checkpoint_totals: result.checkpointTotals,
  };
  fs.writeFileSync(path.join(outDir, 'summary.json'), `${stringifyExact(summary)}\n`);
}

module.exports = { writeOutputs };
''')

Path("/app/src/cli.js").write_text(r'''#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const { loadConfig, parseArgs } = require('./config');
const { simulate } = require('./simulator');
const { writeOutputs } = require('./output');

function main() {
  const { configPath, outDir } = parseArgs(process.argv.slice(2));
  const config = loadConfig(configPath);
  const parent = path.dirname(outDir);
  const base = path.basename(outDir);
  const stageDir = path.join(parent, `.${base}.stage-${process.pid}`);
  const backupDir = path.join(parent, `.${base}.backup-${process.pid}`);
  fs.mkdirSync(parent, { recursive: true });
  fs.rmSync(stageDir, { recursive: true, force: true });
  fs.rmSync(backupDir, { recursive: true, force: true });
  fs.mkdirSync(stageDir);
  let movedExisting = false;
  try {
    const result = simulate(config);
    writeOutputs(config, result, stageDir);
    if (fs.existsSync(outDir)) {
      fs.renameSync(outDir, backupDir);
      movedExisting = true;
    }
    fs.renameSync(stageDir, outDir);
    if (movedExisting) fs.rmSync(backupDir, { recursive: true, force: true });
  } catch (error) {
    fs.rmSync(stageDir, { recursive: true, force: true });
    if (movedExisting && !fs.existsSync(outDir) && fs.existsSync(backupDir)) {
      fs.renameSync(backupDir, outDir);
    }
    throw error;
  }
}

try {
  main();
} catch (error) {
  process.stderr.write(`thermal-cycle: ${error.message}\n`);
  process.exitCode = 1;
}
''')
PY

for config in /app/config/baseline.json /app/config/thin-panel.json; do
  out="/tmp/thermal-cycle-oracle-$(basename "$config" .json)"
  rm -rf "$out"
  node /app/src/cli.js --config "$config" --out "$out"
  test -s "$out/field.csv"
  test -s "$out/events.csv"
  test -s "$out/summary.json"
  test -s "$out/trace.csv"
  test -s "$out/material_profile.csv"
  test -s "$out/stability.csv"
  rm -rf "$out"
done
