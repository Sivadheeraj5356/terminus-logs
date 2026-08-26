const fs = require('fs');
const path = require('path');
const { fieldStats, materialAt } = require('./simulator');

function writeCsv(filePath, header, rows) {
  const lines = [header.join(',')];
  for (const row of rows) lines.push(row.join(','));
  fs.writeFileSync(filePath, `${lines.join('\n')}\n`);
}

function writeOutputs(config, result, outDir) {
  const fieldRows = [];
  for (let x = 0; x < config.width; x += 1) {
    for (let y = 0; y < config.height; y += 1) {
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

  const stats = fieldStats(config, result.temperature, result.cure);
  const values = result.temperature.flat();
  const centerY = Math.floor(config.height / 2);
  const centerX = Math.floor(config.width / 2);
  const centerRowChecksum = result.temperature[centerY].reduce(
    (total, value, x) => total + (x + 1) * value,
    0,
  );
  let centerColumnChecksum = 0;
  for (let y = 0; y < config.height; y += 1) {
    centerColumnChecksum += (y + 1) * result.temperature[y][centerX];
  }
  const summary = {
    scenario: config.scenario,
    width: config.width,
    height: config.height,
    steps: config.steps,
    min_temperature_milli_c: Math.min(...values),
    max_temperature_milli_c: Math.max(...values),
    mean_temperature_milli_c: Math.floor(stats.total_temperature_milli_c / values.length + 0.5),
    hot_cell_count: stats.hot_cell_count,
    full_cure_cell_count: stats.full_cure_cell_count,
    total_temperature_milli_c: stats.total_temperature_milli_c,
    total_cure_ppm: stats.total_cure_ppm,
    center_row_checksum: centerRowChecksum,
    center_column_checksum: centerColumnChecksum,
    event_count: result.events.length,
    first_full_cure_step: result.events.length === 0 ? null : result.events[0].step,
    checkpoint_totals: result.checkpointTotals,
  };
  fs.writeFileSync(path.join(outDir, 'summary.json'), `${JSON.stringify(summary, null, 2)}\n`);
}

module.exports = { writeOutputs };
