const baseUrl = process.argv[2];
if (!baseUrl) {
  process.stderr.write("usage: node /app/safari_dispatch.mjs <base_url>\n");
  process.exit(2);
}

async function readState() {
  const response = await fetch(`${baseUrl}/state`);
  if (!response.ok) throw new Error(`GET /state failed with ${response.status}`);
  return await response.json();
}

async function advance(payload) {
  const response = await fetch(`${baseUrl}/act`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!response.ok) throw new Error(`POST /act failed with ${response.status}`);
  return await response.json();
}

function nextStep(state, from, target) {
  if (from === target) return null;
  const habitats = new Map(state.habitats.map((entry) => [entry.id, entry]));
  const queue = [from];
  const parent = new Map([[from, null]]);
  while (queue.length) {
    const current = queue.shift();
    if (current === target) break;
    for (const neighbor of habitats.get(current).neighbors) {
      if (parent.has(neighbor)) continue;
      parent.set(neighbor, current);
      queue.push(neighbor);
    }
  }
  if (!parent.has(target)) return null;
  let cursor = target;
  while (parent.get(cursor) !== from) cursor = parent.get(cursor);
  return cursor;
}

function nextCommand(state) {
  const explorer = state.explorers.find((entry) => entry.id === "tracker_ama");
  if (explorer.fatigue >= 7) return { type: "rest", explorer_id: explorer.id };
  const target = state.habitats.find((habitat) => habitat.survey_required && !habitat.reported);
  if (!target) return null;
  if (explorer.location === target.id) {
    const sighting = target.sightings.at(-1);
    if (!sighting) return { type: "observe", explorer_id: explorer.id };
    return {
      type: "report",
      explorer_id: explorer.id,
      species_id: sighting.species_id,
      estimate: sighting.observed_count
    };
  }
  const next = nextStep(state, explorer.location, target.id);
  return { type: "move", explorer_id: explorer.id, to: next };
}

let state = await readState();
while (state.status === "active") {
  if (state.summary.reports_filed === state.summary.required_reports && state.turn >= state.limits.finish_floor) {
    state = await advance({ finish: true });
  } else {
    const command = nextCommand(state);
    state = await advance({ commands: command ? [command] : [] });
  }
}

process.stdout.write(`${JSON.stringify({ status: state.status, score: state.score })}\n`);
