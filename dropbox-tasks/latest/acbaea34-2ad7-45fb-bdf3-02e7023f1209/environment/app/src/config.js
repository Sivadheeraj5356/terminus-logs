const fs = require('fs');
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
  integer(config.block_width, 'block_width', 1, 80);
  integer(config.block_height, 'block_height', 1, 80);
  integer(config.material_offset, 'material_offset', 0, Number.MAX_SAFE_INTEGER);
  integer(config.temperature_floor_milli_c, 'temperature_floor_milli_c', -1000000, 1000000);
  integer(config.temperature_ceiling_milli_c, 'temperature_ceiling_milli_c', -1000000, 1000000);
  if (config.temperature_floor_milli_c >= config.temperature_ceiling_milli_c) fail('invalid temperature range');
  integer(config.base_temperature_milli_c, 'base_temperature_milli_c', config.temperature_floor_milli_c, config.temperature_ceiling_milli_c);
  integer(config.activation_temperature_milli_c, 'activation_temperature_milli_c', config.temperature_floor_milli_c, config.temperature_ceiling_milli_c);
  integer(config.base_cure_ppm, 'base_cure_ppm', 0, 1000000);
  integer(config.full_cure_ppm, 'full_cure_ppm', 1, 1000000);

  if (!Array.isArray(config.checkpoint_steps) || config.checkpoint_steps.length < 2) fail('invalid checkpoint_steps');
  config.checkpoint_steps.forEach((step, index) => {
    integer(step, `checkpoint_steps[${index}]`, 0, config.steps);
    if (index > 0 && step <= config.checkpoint_steps[index - 1]) fail('checkpoint_steps must be strictly increasing');
  });
  if (config.checkpoint_steps[0] !== 0 || config.checkpoint_steps.at(-1) !== config.steps) fail('checkpoint_steps must span the run');

  if (!Array.isArray(config.materials) || config.materials.length < 2 || config.materials.length > 5) fail('invalid materials');
  config.materials.forEach((material, index) => {
    if (material === null || Array.isArray(material) || typeof material !== 'object') fail(`invalid material ${index}`);
    for (const key of ['retain', 'horizontal', 'vertical', 'diagonal', 'heater_gain']) {
      integer(material[key], `materials[${index}].${key}`, 0, 1000000);
    }
    integer(material.cure_rate_ppm, `materials[${index}].cure_rate_ppm`, 1, 1000000);
    integer(material.cool_rate_ppm, `materials[${index}].cool_rate_ppm`, 1, 1000000);
    const denominator = material.retain + 2 * material.horizontal + 2 * material.vertical + 4 * material.diagonal;
    if (denominator <= 0) fail(`material ${index} has zero stencil weight`);
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
    integer(hotspot.peak_milli_c, `hotspots[${index}].peak_milli_c`, 0, 1000000);
    integer(hotspot.decay_per_cell_milli_c, `hotspots[${index}].decay_per_cell_milli_c`, 0, 1000000);
  });

  if (!Array.isArray(config.heater_pulses)) fail('invalid heater_pulses');
  config.heater_pulses.forEach((pulse, index) => {
    if (pulse === null || Array.isArray(pulse) || typeof pulse !== 'object') fail(`invalid heater_pulse ${index}`);
    integer(pulse.start_step, `heater_pulses[${index}].start_step`, 1, config.steps);
    integer(pulse.end_step, `heater_pulses[${index}].end_step`, pulse.start_step, config.steps);
    integer(pulse.x, `heater_pulses[${index}].x`, 0, config.width - 1);
    integer(pulse.y, `heater_pulses[${index}].y`, 0, config.height - 1);
    integer(pulse.strength_milli_c, `heater_pulses[${index}].strength_milli_c`, 0, 1000000);
    integer(pulse.decay_per_cell_milli_c, `heater_pulses[${index}].decay_per_cell_milli_c`, 0, 1000000);
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
