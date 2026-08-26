#!/usr/bin/env node

const fs = require("fs");
const path = require("path");

function main() {
  const inputDir = process.argv[2] || "/app/task_file/input_data";
  const outputDir = process.argv[3] || "/app/task_file/output_data";
  fs.mkdirSync(outputDir, { recursive: true });

  const placeholder = {
    selected: [],
    deferred: [],
    rejected: [],
    summary: {
      selected_count: 0,
      deferred_count: 0,
      rejected_count: 0,
      total_value: 0,
      total_risk: 0,
      by_env: {},
      by_window: {},
    },
  };

  fs.writeFileSync(
    path.join(outputDir, "deployment_decisions.json"),
    JSON.stringify(placeholder, null, 2) + "\n"
  );
  console.error(`placeholder adjudicator read ${inputDir}`);
}

main();
