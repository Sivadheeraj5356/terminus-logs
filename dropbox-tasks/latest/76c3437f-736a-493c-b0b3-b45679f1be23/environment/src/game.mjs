const PHASES = ["dawn", "day", "dusk", "night"];

const SPECIES = [
  { id: "zebra", label: "plains zebra", group: "mammal", preferredPhase: "dawn" },
  { id: "giraffe", label: "giraffe", group: "mammal", preferredPhase: "day" },
  { id: "elephant", label: "savanna elephant", group: "mammal", preferredPhase: "dawn" },
  { id: "wildebeest", label: "blue wildebeest", group: "mammal", preferredPhase: "dusk" },
  { id: "lion", label: "lion", group: "mammal", preferredPhase: "dusk" },
  { id: "hyena", label: "spotted hyena", group: "mammal", preferredPhase: "night" },
  { id: "pangolin", label: "ground pangolin", group: "mammal", preferredPhase: "night" },
  { id: "secretary_bird", label: "secretary bird", group: "bird", preferredPhase: "day" },
  { id: "ground_hornbill", label: "southern ground hornbill", group: "bird", preferredPhase: "dawn" },
  { id: "kori_bustard", label: "kori bustard", group: "bird", preferredPhase: "dusk" },
  { id: "eagle_owl", label: "Verreaux's eagle-owl", group: "bird", preferredPhase: "night" },
  { id: "bee_eater", label: "white-fronted bee-eater", group: "bird", preferredPhase: "day" }
];

const SPECIES_BY_ID = new Map(SPECIES.map((entry) => [entry.id, entry]));

const PROFILES = {
  open_savanna: {
    label: "Open savanna transect",
    siteCount: 10,
    finishFloor: 42,
    turnLimit: 66,
    riskShift: -0.08,
    weather: ["clear", "clear", "wind", "clear", "clear", "haze", "clear", "clear"],
    habitats: ["grass pan", "acacia edge", "kopje", "salt lick", "seasonal pool", "termite plain"],
    extraLinks: [["habitat_2", "habitat_7"], ["habitat_4", "habitat_9"]]
  },
  river_confluence: {
    label: "River confluence circuit",
    siteCount: 10,
    finishFloor: 42,
    turnLimit: 68,
    riskShift: 0.08,
    weather: ["mist", "clear", "clear", "rain", "clear", "clear", "wind", "clear"],
    habitats: ["reed margin", "gallery forest", "sand bank", "oxbow", "flood meadow", "river bluff"],
    extraLinks: [["habitat_1", "habitat_6"], ["habitat_3", "habitat_8"], ["habitat_5", "habitat_10"]]
  },
  thornveld_dusk: {
    label: "Thornveld dusk circuit",
    siteCount: 10,
    finishFloor: 42,
    turnLimit: 70,
    riskShift: 0.13,
    weather: ["clear", "heat", "clear", "clear", "dust", "heat", "clear", "clear"],
    habitats: ["thorn scrub", "dry wash", "baobab rise", "rock shelf", "brush hollow", "open glade"],
    extraLinks: [["habitat_2", "habitat_5"], ["habitat_6", "habitat_9"], ["habitat_3", "habitat_10"]]
  }
};

function rngFor(seed) {
  let value = (Number(seed) ^ 0x9e3779b9) >>> 0;
  return () => {
    value ^= value << 13;
    value ^= value >>> 17;
    value ^= value << 5;
    return (value >>> 0) / 4294967296;
  };
}

function shuffled(values, random) {
  const copy = [...values];
  for (let index = copy.length - 1; index > 0; index -= 1) {
    const swap = Math.floor(random() * (index + 1));
    [copy[index], copy[swap]] = [copy[swap], copy[index]];
  }
  return copy;
}

function stableRoll(...parts) {
  let hash = 2166136261;
  for (const character of parts.join("|").split("")) {
    hash ^= character.charCodeAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

function routeId(left, right) {
  return [left, right].sort().join("--");
}

function topologyLinks(profile) {
  const links = [["base", "habitat_1"], [`habitat_${profile.siteCount}`, "base"]];
  for (let index = 1; index < profile.siteCount; index += 1) {
    links.push([`habitat_${index}`, `habitat_${index + 1}`]);
  }
  for (const link of profile.extraLinks || []) links.push(link);
  return links;
}

function riskFromRoll(roll, shift) {
  const adjusted = Math.max(0, Math.min(0.999, roll + shift));
  if (adjusted < 0.38) return "low";
  if (adjusted < 0.76) return "moderate";
  return "high";
}

function conditionAt(game, turn) {
  const profile = PROFILES[game.scenarioId];
  return {
    phase: PHASES[turn % PHASES.length],
    weather: profile.weather[turn % profile.weather.length]
  };
}

function makeHabitats(profile, random, speciesOrder) {
  const habitats = [{
    id: "base",
    label: "field base",
    habitat: "operations camp",
    surveyRequired: false,
    neighbors: [],
    hiddenSpeciesId: null,
    hiddenCount: null,
    sightings: [],
    report: null,
    disturbance: 0
  }];
  for (let index = 1; index <= profile.siteCount; index += 1) {
    habitats.push({
      id: `habitat_${index}`,
      label: `survey habitat ${index}`,
      habitat: profile.habitats[(index - 1 + Math.floor(random() * profile.habitats.length)) % profile.habitats.length],
      surveyRequired: true,
      neighbors: [],
      hiddenSpeciesId: speciesOrder[index - 1].id,
      hiddenCount: 3 + Math.floor(random() * 8),
      sightings: [],
      report: null,
      disturbance: 0
    });
  }
  const byId = new Map(habitats.map((entry) => [entry.id, entry]));
  for (const [left, right] of topologyLinks(profile)) {
    const leftHabitat = byId.get(left);
    const rightHabitat = byId.get(right);
    if (!leftHabitat || !rightHabitat) continue;
    if (!leftHabitat.neighbors.includes(right)) leftHabitat.neighbors.push(right);
    if (!rightHabitat.neighbors.includes(left)) rightHabitat.neighbors.push(left);
  }
  return habitats;
}

function makeRoutes(profile, random) {
  const routes = [];
  const seen = new Set();
  for (const [left, right] of topologyLinks(profile)) {
    const id = routeId(left, right);
    if (seen.has(id)) continue;
    seen.add(id);
    routes.push({
      id,
      left,
      right,
      actualRisk: riskFromRoll(random(), profile.riskShift),
      assessed: false,
      assessedBy: null
    });
  }
  return routes;
}

function makeExplorers() {
  return [
    { id: "tracker_ama", label: "Ama", role: "tracker", specialty: "routes", pair: "north", location: "base", fatigue: 0 },
    { id: "spotter_jo", label: "Jo", role: "wildlife spotter", specialty: "mammal", pair: "north", location: "base", fatigue: 0 },
    { id: "ranger_kito", label: "Kito", role: "ranger", specialty: "safety", pair: "south", location: "base", fatigue: 0 },
    { id: "ornithologist_lei", label: "Lei", role: "ornithologist", specialty: "bird", pair: "south", location: "base", fatigue: 0 }
  ];
}

export function scenarioIds() {
  return Object.keys(PROFILES);
}

export function scenarioCatalog() {
  return Object.entries(PROFILES).map(([id, profile]) => ({
    id,
    label: profile.label,
    survey_habitats: profile.siteCount,
    finish_floor: profile.finishFloor,
    turn_limit: profile.turnLimit
  }));
}

export function createGame(scenarioId, seed) {
  const profile = PROFILES[scenarioId];
  if (!profile) throw new Error("unknown scenario");
  const random = rngFor(seed);
  const speciesOrder = shuffled(SPECIES, random).slice(0, profile.siteCount);
  return {
    scenarioId,
    seed,
    status: "active",
    endReason: null,
    turn: 0,
    habitats: makeHabitats(profile, random, speciesOrder),
    routes: makeRoutes(profile, random),
    explorers: makeExplorers(),
    events: [],
    metrics: {
      commands: 0,
      highLoadTurns: 0,
      observations: 0,
      highSightings: 0,
      assessedRoutes: 0,
      safePairedCrossings: 0,
      lowRiskCrossings: 0,
      highRiskCrossings: 0,
      unsupportedRisk: 0,
      safetyIncidents: 0,
      invalidCommands: 0,
      disturbanceEvents: 0,
      reportsFiled: 0,
      correctReports: 0,
      inaccurateReports: 0
    }
  };
}

function profileFor(game) {
  return PROFILES[game.scenarioId];
}

function habitatFor(game, id) {
  return game.habitats.find((entry) => entry.id === id);
}

function explorerFor(game, id) {
  return game.explorers.find((entry) => entry.id === id);
}

function routeFor(game, left, right) {
  return game.routes.find((entry) => entry.id === routeId(left, right));
}

function addEvent(game, type, message, details = {}) {
  game.events.push({ turn: game.turn, type, message, ...details });
  if (game.events.length > 40) game.events.splice(0, game.events.length - 40);
}

function reject(game, command, reason, rejected) {
  game.metrics.invalidCommands += 1;
  rejected.push({ command, reason });
  addEvent(game, "rejected", reason, { explorer_id: command?.explorer_id || null });
}

function processAssessment(game, explorer, command, accepted, rejected) {
  const destination = String(command.to || "");
  const route = routeFor(game, explorer.location, destination);
  if (!route) return reject(game, command, "route is not adjacent", rejected);
  if (route.assessed) return reject(game, command, "route is already assessed", rejected);
  route.assessed = true;
  route.assessedBy = explorer.id;
  explorer.fatigue = Math.min(10, explorer.fatigue + (explorer.specialty === "routes" ? 0.1 : 0.35));
  game.metrics.assessedRoutes += 1;
  accepted.push(command);
  addEvent(game, "route_assessed", `${explorer.label} assessed ${route.id}`, { route_id: route.id, risk: route.actualRisk });
}

function processRest(game, explorer, command, accepted) {
  explorer.fatigue = Math.max(0, explorer.fatigue - (explorer.location === "base" ? 5 : 3.5));
  accepted.push(command);
  addEvent(game, "rest", `${explorer.label} rested`, { explorer_id: explorer.id });
}

function observationQuality(game, explorer, habitat, species) {
  const conditions = conditionAt(game, game.turn);
  const activePhase = conditions.phase === species.preferredPhase;
  const blockingWeather = ["rain", "dust"].includes(conditions.weather);
  const roleMatch = explorer.specialty === species.group;
  const enoughEvidence = habitat.sightings.length >= 1;
  if (activePhase && !blockingWeather && explorer.fatigue <= 7 && habitat.disturbance <= 2 && (roleMatch || enoughEvidence)) {
    return "high";
  }
  if ((activePhase || roleMatch) && explorer.fatigue <= 8 && habitat.disturbance <= 4) return "medium";
  return "low";
}

function processObservation(game, explorer, command, accepted, rejected, observedHabitats) {
  const habitat = habitatFor(game, explorer.location);
  if (!habitat?.surveyRequired) return reject(game, command, "explorer is not at a survey habitat", rejected);
  if (habitat.report) return reject(game, command, "habitat report is already locked", rejected);
  const species = SPECIES_BY_ID.get(habitat.hiddenSpeciesId);
  const quality = observationQuality(game, explorer, habitat, species);
  const miss = quality === "high" ? 0 : quality === "medium"
    ? 1 + (stableRoll(game.seed, habitat.id, game.turn, explorer.id) % 2)
    : 2 + (stableRoll(game.seed, explorer.id, habitat.id, game.turn) % 3);
  const sighting = {
    id: `sighting_${habitat.sightings.length + 1}`,
    turn: game.turn,
    explorer_id: explorer.id,
    species_id: species.id,
    species_label: species.label,
    group: species.group,
    observed_count: Math.max(1, habitat.hiddenCount - miss),
    quality,
    preferred_phase: species.preferredPhase,
    phase: conditionAt(game, game.turn).phase,
    weather: conditionAt(game, game.turn).weather
  };
  habitat.sightings.push(sighting);
  habitat.disturbance = Math.min(8, habitat.disturbance + 2);
  explorer.fatigue = Math.min(10, explorer.fatigue + 0.65);
  game.metrics.observations += 1;
  if (quality === "high" && !habitat.sightings.slice(0, -1).some((entry) => entry.quality === "high")) {
    game.metrics.highSightings += 1;
  }
  if (habitat.disturbance >= 5) game.metrics.disturbanceEvents += 1;
  observedHabitats.add(habitat.id);
  accepted.push(command);
  addEvent(game, "sighting", `${explorer.label} logged a ${quality} sighting at ${habitat.label}`, {
    habitat_id: habitat.id,
    species_id: species.id,
    observed_count: sighting.observed_count,
    quality
  });
}

function processReport(game, explorer, command, accepted, rejected) {
  const habitat = habitatFor(game, explorer.location);
  if (!habitat?.surveyRequired) return reject(game, command, "explorer is not at a survey habitat", rejected);
  if (habitat.report) return reject(game, command, "habitat report is already locked", rejected);
  if (!habitat.sightings.length) return reject(game, command, "no sighting supports this report", rejected);
  const speciesId = String(command.species_id || "");
  const estimate = Number(command.estimate);
  if (!SPECIES_BY_ID.has(speciesId) || !Number.isInteger(estimate) || estimate < 1 || estimate > 20) {
    return reject(game, command, "report species and estimate are out of range", rejected);
  }
  const correct = speciesId === habitat.hiddenSpeciesId && estimate === habitat.hiddenCount;
  habitat.report = { explorer_id: explorer.id, species_id: speciesId, estimate, turn: game.turn, correct };
  explorer.fatigue = Math.min(10, explorer.fatigue + 0.15);
  game.metrics.reportsFiled += 1;
  if (correct) game.metrics.correctReports += 1;
  else game.metrics.inaccurateReports += 1;
  accepted.push(command);
  addEvent(game, "report_filed", `${explorer.label} locked the count for ${habitat.label}`, {
    habitat_id: habitat.id,
    species_id: speciesId,
    estimate
  });
}

function processMoves(game, moveRows, accepted, rejected) {
  const groups = new Map();
  for (const row of moveRows) {
    const { explorer, command } = row;
    const destination = String(command.to || "");
    const route = routeFor(game, explorer.location, destination);
    if (!route) {
      reject(game, command, "route is not adjacent", rejected);
      continue;
    }
    if (explorer.fatigue >= 9.5) {
      reject(game, command, "explorer is too fatigued to move", rejected);
      continue;
    }
    const key = `${explorer.location}->${destination}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push({ explorer, command, route, destination });
  }
  for (const rows of groups.values()) {
    const paired = rows.length >= 2;
    const route = rows[0].route;
    const skilledSolo = rows[0].explorer.specialty === "routes" || rows[0].explorer.specialty === "safety";
    const supported = route.assessed && (
      route.actualRisk === "low" ||
      (route.actualRisk === "moderate" && (paired || skilledSolo)) ||
      (route.actualRisk === "high" && paired)
    );
    if (paired && supported) {
      game.metrics.safePairedCrossings += 1;
      addEvent(game, "paired_crossing", `A field pair crossed ${route.id}`, { route_id: route.id });
    }
    for (const { explorer, command, destination } of rows) {
      const roleReduction = explorer.specialty === "safety" ? 0.25 : explorer.specialty === "routes" ? 0.15 : 0;
      const riskFatigue = { low: 0.1, moderate: 0.45, high: 0.9 }[route.actualRisk];
      explorer.location = destination;
      explorer.fatigue = Math.min(10, explorer.fatigue + 0.8 + riskFatigue - roleReduction);
      if (route.assessed && route.actualRisk === "low") game.metrics.lowRiskCrossings += 1;
      if (route.assessed && route.actualRisk === "high") game.metrics.highRiskCrossings += 1;
      if (!supported) {
        game.metrics.unsupportedRisk += 1;
        const incidentLimit = route.actualRisk === "high" ? 4 : route.actualRisk === "moderate" ? 2 : 1;
        if (stableRoll(game.seed, game.turn, explorer.id, route.id) % 5 < incidentLimit) {
          game.metrics.safetyIncidents += 1;
          explorer.fatigue = Math.min(10, explorer.fatigue + 1.5);
          addEvent(game, "safety_incident", `${explorer.label} had an unsupported crossing incident`, {
            explorer_id: explorer.id,
            route_id: route.id
          });
        } else {
          addEvent(game, "unsupported_risk", `${explorer.label} crossed without adequate support`, {
            explorer_id: explorer.id,
            route_id: route.id
          });
        }
      }
      accepted.push(command);
      addEvent(game, "move", `${explorer.label} moved to ${destination}`, { explorer_id: explorer.id, to: destination });
    }
  }
}

function currentScore(game) {
  const profile = profileFor(game);
  const metrics = game.metrics;
  const reportedHabitats = game.habitats.filter((entry) => entry.report);
  const distinctSpecies = new Set(reportedHabitats.map((entry) => entry.report.species_id)).size;
  const earlyReportTurns = reportedHabitats.reduce(
    (sum, entry) => sum + Math.max(0, profile.finishFloor - entry.report.turn),
    0
  );
  const positive = {
    filed_counts: metrics.reportsFiled * 300,
    accurate_counts: metrics.correctReports * 550,
    distinct_species: distinctSpecies * 100,
    reliable_sightings: metrics.highSightings * 300,
    route_assessment: metrics.assessedRoutes * 75,
    paired_crossings: Math.min(metrics.safePairedCrossings, 20) * 75,
    low_risk_crossings: Math.min(metrics.lowRiskCrossings, 20) * 15,
    early_reports: earlyReportTurns * 20,
    submission: game.status === "complete" ? 1500 : 0,
    remaining_field_time: game.status === "complete" ? Math.max(0, profile.turnLimit - game.turn) * 40 : 0,
    clean_safety_record: game.status === "complete" && metrics.safetyIncidents === 0 && metrics.unsupportedRisk === 0 ? 1800 : 0
  };
  const negative = {
    elapsed_turns: game.turn * 25,
    commands: metrics.commands * 25,
    high_load_turns: metrics.highLoadTurns * 20,
    unsupported_risk: metrics.unsupportedRisk * 1000,
    safety_incidents: metrics.safetyIncidents * 1800,
    high_risk_crossings: metrics.highRiskCrossings * 100,
    invalid_commands: metrics.invalidCommands * 350,
    disturbance: metrics.disturbanceEvents * 200,
    inaccurate_counts: metrics.inaccurateReports * 400
  };
  const score = Object.values(positive).reduce((sum, value) => sum + value, 0)
    - Object.values(negative).reduce((sum, value) => sum + value, 0);
  return { score, positive, negative };
}

function reportView(habitat) {
  if (!habitat.report) return null;
  return {
    explorer_id: habitat.report.explorer_id,
    species_id: habitat.report.species_id,
    estimate: habitat.report.estimate,
    turn: habitat.report.turn,
    locked: true
  };
}

function routeView(route) {
  return {
    id: route.id,
    endpoints: [route.left, route.right],
    assessed: route.assessed,
    risk: route.assessed ? route.actualRisk : "unknown",
    assessed_by: route.assessedBy
  };
}

function legalActions(game) {
  const actions = [];
  for (const explorer of game.explorers) {
    const habitat = habitatFor(game, explorer.location);
    for (const neighbor of habitat.neighbors) {
      const route = routeFor(game, explorer.location, neighbor);
      if (!route.assessed) actions.push({ type: "assess_route", explorer_id: explorer.id, to: neighbor });
      actions.push({ type: "move", explorer_id: explorer.id, to: neighbor });
    }
    if (habitat.surveyRequired && !habitat.report) {
      actions.push({ type: "observe", explorer_id: explorer.id });
      if (habitat.sightings.length) actions.push({ type: "report", explorer_id: explorer.id });
    }
    actions.push({ type: "rest", explorer_id: explorer.id });
  }
  return actions;
}

export function publicState(game) {
  const profile = profileFor(game);
  const score = currentScore(game);
  const reports = game.habitats.filter((entry) => entry.report).map((entry) => ({ habitat_id: entry.id, ...reportView(entry) }));
  return {
    status: game.status,
    end_reason: game.endReason,
    turn: game.turn,
    turn_limit: profile.turnLimit,
    score: score.score,
    scenario: { id: game.scenarioId, label: profile.label },
    limits: { max_commands_per_turn: 4, finish_floor: profile.finishFloor },
    conditions: conditionAt(game, game.turn),
    forecast: Array.from({ length: 4 }, (_, offset) => ({ turn: game.turn + offset, ...conditionAt(game, game.turn + offset) })),
    habitats: game.habitats.map((entry) => ({
      id: entry.id,
      label: entry.label,
      habitat: entry.habitat,
      survey_required: entry.surveyRequired,
      neighbors: [...entry.neighbors],
      disturbance: entry.disturbance,
      reported: Boolean(entry.report),
      report: reportView(entry),
      sightings: entry.sightings.map((sighting) => ({ ...sighting }))
    })),
    routes: game.routes.map(routeView),
    explorers: game.explorers.map((entry) => ({ ...entry, fatigue: Number(entry.fatigue.toFixed(2)) })),
    reports,
    summary: {
      required_reports: profile.siteCount,
      reports_filed: game.metrics.reportsFiled,
      reliable_sightings: game.metrics.highSightings,
      routes_assessed: game.metrics.assessedRoutes,
      safe_paired_crossings: game.metrics.safePairedCrossings,
      low_risk_crossings: game.metrics.lowRiskCrossings,
      high_risk_crossings: game.metrics.highRiskCrossings,
      unsupported_risk: game.metrics.unsupportedRisk,
      safety_incidents: game.metrics.safetyIncidents,
      commands_submitted: game.metrics.commands,
      objective_reached: game.metrics.reportsFiled === profile.siteCount,
      completed_turn: game.status === "complete" ? game.turn : null
    },
    scoreboard: { ...score.positive, ...Object.fromEntries(Object.entries(score.negative).map(([key, value]) => [key, -value])) },
    action_schema: {
      assess_route: { required: ["type", "explorer_id", "to"] },
      move: { required: ["type", "explorer_id", "to"] },
      observe: { required: ["type", "explorer_id"] },
      report: { required: ["type", "explorer_id", "species_id", "estimate"], estimate: { min: 1, max: 20 } },
      rest: { required: ["type", "explorer_id"] },
      finish: { body: { finish: true } }
    },
    legal_actions: game.status === "active" ? legalActions(game) : [],
    recent_events: game.events.slice(-14).map((entry) => ({ ...entry }))
  };
}

export function advanceGame(game, payload) {
  if (game.status !== "active") return { ok: false, accepted: [], rejected: [{ reason: "census is not active" }] };
  const profile = profileFor(game);
  if (payload?.finish === true) {
    if (game.turn >= profile.finishFloor && game.metrics.reportsFiled === profile.siteCount) {
      game.status = "complete";
      game.endReason = "census_submitted";
      addEvent(game, "complete", "The safari census was submitted");
      return { ok: true, accepted: [{ finish: true }], rejected: [] };
    }
    game.metrics.invalidCommands += 1;
    addEvent(game, "rejected", "The census is not ready for submission");
  }

  const submitted = Array.isArray(payload?.commands) ? payload.commands : [];
  const commands = submitted.slice(0, 4);
  if (submitted.length > 4) game.metrics.invalidCommands += submitted.length - 4;
  game.metrics.commands += commands.length;
  if (commands.length === 4) game.metrics.highLoadTurns += 1;
  const accepted = [];
  const rejected = [];
  const used = new Set();
  const moveRows = [];
  const observedHabitats = new Set();

  for (const command of commands) {
    if (!command || typeof command !== "object") {
      reject(game, command, "command must be an object", rejected);
      continue;
    }
    const explorer = explorerFor(game, String(command.explorer_id || ""));
    if (!explorer) {
      reject(game, command, "unknown explorer_id", rejected);
      continue;
    }
    if (used.has(explorer.id)) {
      reject(game, command, "explorer already has a command this turn", rejected);
      continue;
    }
    used.add(explorer.id);
    if (command.type === "move") {
      moveRows.push({ explorer, command });
    } else if (command.type === "assess_route") {
      processAssessment(game, explorer, command, accepted, rejected);
    } else if (command.type === "observe") {
      processObservation(game, explorer, command, accepted, rejected, observedHabitats);
    } else if (command.type === "report") {
      processReport(game, explorer, command, accepted, rejected);
    } else if (command.type === "rest") {
      processRest(game, explorer, command, accepted);
    } else {
      reject(game, command, "unknown command type", rejected);
    }
  }

  processMoves(game, moveRows, accepted, rejected);
  for (const habitat of game.habitats) {
    if (!observedHabitats.has(habitat.id)) habitat.disturbance = Math.max(0, habitat.disturbance - 1);
  }
  game.turn += 1;
  if (game.turn >= profile.turnLimit && game.status === "active") {
    game.status = "failed";
    game.endReason = "field_window_closed";
    addEvent(game, "failed", "The field window closed before submission");
  }
  return { ok: true, accepted, rejected };
}
