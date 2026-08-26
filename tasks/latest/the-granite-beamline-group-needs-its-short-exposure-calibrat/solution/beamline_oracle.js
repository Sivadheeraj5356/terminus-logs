#!/usr/bin/env node
const fs = require("fs");
const path = require("path");

const args = process.argv.slice(2);
const inputPath = args[0] || "/app/task_file/beamline_case.json";
const outputDir = args[1] || "/app/task_file/output";

function r2(value) {
  return Math.round((value + 1e-9) * 100) / 100;
}

function centi(value) {
  return Math.floor(value * 100 + 0.5 + 1e-7);
}

function byId(rows) {
  const out = {};
  for (const row of rows) out[row.id] = row;
  return out;
}

function sortedKeys(obj) {
  return Object.keys(obj).sort();
}

function profileSingle(data, profile) {
  const protons = data.protons_per_spill;
  const horns = byId(data.horns);
  const heat = {};
  const flux = {};
  for (const hid of sortedKeys(horns)) heat[hid] = (profile.heat_mj[hid] || 0) * protons;
  for (const bin of data.bins) flux[bin.id] = (profile.flux[bin.id] || 0) * bin.response * protons;
  const dose = profile.shield_dose * protons;
  const windowHeat = Object.values(heat).reduce((a, b) => a + b, 0) + data.cooldown_reserve_mj;
  const blockers = [];
  if (windowHeat > data.max_window_heat_mj + 1e-9) blockers.push("window_heat");
  for (const horn of data.horns) {
    if (Math.abs(profile.currents_ka[horn.id] || 0) > horn.current_limit_ka + 1e-9) blockers.push(`current:${horn.id}`);
  }
  blockers.sort();
  return {
    profile_id: profile.id,
    bin_flux: sortedKeys(flux).map((bid) => ({ bin: bid, flux: r2(flux[bid]) })),
    horn_heat_mj: sortedKeys(heat).map((hid) => ({ horn: hid, heat_mj: r2(heat[hid]) })),
    shield_dose: r2(dose),
    window_heat_mj: r2(windowHeat),
    feasible: blockers.length === 0,
    blockers,
  };
}

function profileScreen(data) {
  return [...data.profiles].sort((a, b) => a.id.localeCompare(b.id)).map((p) => profileSingle(data, p));
}

function transitionOk(data, prev, cur) {
  for (const horn of data.horns) {
    const a = prev.currents_ka[horn.id] || 0;
    const b = cur.currents_ka[horn.id] || 0;
    if (Math.abs(a) > 1e-9 && Math.abs(b) > 1e-9 && Math.abs(a - b) > data.max_current_delta_ka + 1e-9) return false;
  }
  return true;
}

function evaluate(data, ids) {
  const profiles = byId(data.profiles);
  const horns = byId(data.horns);
  const temps = {};
  const totals = {};
  for (const horn of data.horns) temps[horn.id] = horn.base_temp_k;
  for (const bin of data.bins) totals[bin.id] = 0;
  let dose = 0;
  let peakTemp = Math.max(...Object.values(temps));
  let prior = null;
  let changes = 0;
  const rows = [];
  const blockers = new Set();

  ids.forEach((pid, idx) => {
    const slot = idx + 1;
    const prof = profiles[pid];
    if (prior) {
      if (!transitionOk(data, prior, prof)) blockers.add(`current_delta:${slot}`);
      if (pid !== prior.id && pid !== "idle" && prior.id !== "idle") changes += 1;
    }
    prior = prof;

    for (const horn of data.horns) {
      temps[horn.id] = Math.max(horn.base_temp_k, temps[horn.id] - horn.cool_rate_k);
    }

    const single = profileSingle(data, prof);
    for (const b of single.blockers) blockers.add(b);
    dose += prof.shield_dose * data.protons_per_spill;
    for (const bin of data.bins) {
      totals[bin.id] += (prof.flux[bin.id] || 0) * bin.response * data.protons_per_spill;
    }
    for (const horn of data.horns) {
      const heat = (prof.heat_mj[horn.id] || 0) * data.protons_per_spill;
      temps[horn.id] += heat / horn.thermal_capacity_mj_per_k;
      peakTemp = Math.max(peakTemp, temps[horn.id]);
      if (temps[horn.id] > data.max_horn_temp_k + 1e-9) blockers.add(`horn_temp:${horn.id}`);
    }
    if (dose > data.max_shield_dose + 1e-9) blockers.add("shield_dose");
    rows.push({
      slot,
      profile_id: pid,
      horn_temps_k: sortedKeys(temps).map((hid) => ({ horn: hid, temp_k: r2(temps[hid]) })),
      cumulative_flux: sortedKeys(totals).map((bid) => ({ bin: bid, flux: r2(totals[bid]) })),
      cumulative_shield_dose: r2(dose),
    });
  });

  let under = 0;
  let over = 0;
  for (const bin of data.bins) {
    const actual = totals[bin.id];
    if (actual + 1e-9 < bin.min_flux) {
      under += bin.min_flux - actual;
      blockers.add(`flux:${bin.id}`);
    } else {
      over += actual - bin.min_flux;
    }
  }

  const signature = ids.map((pid, i) => `${i + 1}:${pid}`).join("|");
  const objective = [centi(under), centi(over), centi(peakTemp), centi(dose), changes, signature];
  return {
    ok: blockers.size === 0,
    blockers: [...blockers].sort(),
    payload: {
      ids,
      rows,
      totals: sortedKeys(totals).map((bid) => ({ bin: bid, flux: r2(totals[bid]) })),
      dose: r2(dose),
      peak_temp_k: r2(peakTemp),
      objective,
    },
  };
}

function compareObjective(a, b) {
  for (let i = 0; i < a.length; i++) {
    if (a[i] < b[i]) return -1;
    if (a[i] > b[i]) return 1;
  }
  return 0;
}

function blocked(screen, blockers) {
  return {
    "beam_plan.json": { status: "blocked", objective: [], assignments: [], blockers: [...blockers].sort() },
    "profile_screen.json": { profiles: screen },
    "thermal_trace.json": { slots: [], final_flux: [], peak_temp_k: 0.0, shield_dose: 0.0 },
  };
}

function solve(data) {
  const screen = profileScreen(data);
  const feasible = screen.filter((row) => row.feasible).map((row) => row.profile_id).sort();
  if (feasible.length === 0) return blocked(screen, ["no_screen_profile"]);
  let best = null;
  let bestPayload = null;
  const allBlockers = new Set();
  const ids = new Array(data.spill_count);

  function dfs(pos) {
    if (pos === ids.length) {
      const result = evaluate(data, ids.slice());
      if (!result.ok) {
        for (const b of result.blockers) allBlockers.add(b);
        return;
      }
      if (best === null || compareObjective(result.payload.objective, best) < 0) {
        best = result.payload.objective;
        bestPayload = result.payload;
      }
      return;
    }
    for (const pid of feasible) {
      ids[pos] = pid;
      dfs(pos + 1);
    }
  }

  dfs(0);
  if (!bestPayload) return blocked(screen, allBlockers.size ? [...allBlockers] : ["no_valid_schedule"]);
  return {
    "beam_plan.json": {
      status: "ok",
      objective: bestPayload.objective,
      assignments: bestPayload.ids.map((pid, i) => ({ slot: i + 1, profile_id: pid })),
      blockers: [],
    },
    "profile_screen.json": { profiles: screen },
    "thermal_trace.json": {
      slots: bestPayload.rows,
      final_flux: bestPayload.totals,
      peak_temp_k: bestPayload.peak_temp_k,
      shield_dose: bestPayload.dose,
    },
  };
}

const data = JSON.parse(fs.readFileSync(inputPath, "utf8"));
const out = solve(data);
fs.rmSync(outputDir, { recursive: true, force: true });
fs.mkdirSync(outputDir, { recursive: true });
for (const name of ["beam_plan.json", "profile_screen.json", "thermal_trace.json"]) {
  fs.writeFileSync(path.join(outputDir, name), JSON.stringify(out[name], null, 2) + "\n");
}
