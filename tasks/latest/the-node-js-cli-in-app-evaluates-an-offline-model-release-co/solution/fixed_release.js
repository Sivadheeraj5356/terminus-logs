const crypto = require("crypto");

function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function subjectMap(subjects) {
  const by = new Map();
  for (const subject of asArray(subjects)) {
    by.set(subject.id, subject);
    for (const alias of asArray(subject.aliases)) by.set(alias, subject);
  }
  return by;
}

function latestRelease(releases, model, at) {
  let best = null;
  asArray(releases).forEach((release, index) => {
    if (release.model !== model) return;
    if (release.effective === undefined || release.effective > at) return;
    if (release.expires !== undefined && at >= release.expires) return;
    if (!best || release.effective > best.release.effective || (release.effective === best.release.effective && index > best.index)) {
      best = { release, index };
    }
  });
  return best ? best.release : null;
}

function matchesWhen(subject, when) {
  for (const [key, expected] of Object.entries(when || {})) {
    const actual = (subject.attrs || {})[key];
    if (Array.isArray(expected)) {
      if (!expected.includes(actual)) return false;
    } else if (actual !== expected) {
      return false;
    }
  }
  return true;
}

function bucket(salt, model, subject) {
  const hex = crypto.createHash("sha256").update(`${salt || ""}|${model}|${subject}`).digest("hex").slice(0, 8);
  return parseInt(hex, 16) / 0x100000000;
}

function selectVariant(release, subjectId, subjectRecord, at) {
  let override = null;
  asArray(release.overrides).forEach((item) => {
    if (item.subject === subjectId && (item.until === undefined || at < item.until)) override = item;
  });
  if (override) return { variant: override.variant, source: `${release.id}:override:${subjectId}` };

  let cohort = null;
  asArray(release.cohorts).forEach((item, index) => {
    if (!matchesWhen(subjectRecord, item.when)) return;
    if (!cohort || (item.priority || 0) > (cohort.item.priority || 0) || ((item.priority || 0) === (cohort.item.priority || 0) && index > cohort.index)) {
      cohort = { item, index };
    }
  });
  if (cohort) return { variant: cohort.item.variant, source: `${release.id}:cohort:${cohort.item.id}` };

  let acc = 0;
  const b = bucket(release.salt, release.model, subjectId);
  for (const variant of asArray(release.variants)) {
    acc += Number(variant.weight || 0);
    if (b < acc) return { variant: variant.id, source: `${release.id}:rollout` };
  }
  if (release.default !== undefined) return { variant: release.default, source: `${release.id}:default` };
  return { variant: null, source: null };
}

function evaluateReleases(input) {
  const subjects = subjectMap(input.subjects);
  const memo = new Map();
  const stack = new Set();

  function evalOne(model, subjectId, at) {
    const key = `${model}|${subjectId}|${at}`;
    if (stack.has(key)) return { status: "blocked", variant: null, source: null, blockedBy: "cycle" };
    if (memo.has(key)) return memo.get(key);
    stack.add(key);
    const release = latestRelease(input.releases, model, at);
    if (!release) {
      const missing = { status: "missing", variant: null, source: null, blockedBy: null };
      memo.set(key, missing);
      stack.delete(key);
      return missing;
    }
    for (const prereq of asArray(release.prerequisites)) {
      const dep = evalOne(prereq.model, subjectId, at);
      if (dep.blockedBy === "cycle") {
        const blocked = { status: "blocked", variant: null, source: null, blockedBy: "cycle" };
        memo.set(key, blocked);
        stack.delete(key);
        return blocked;
      }
      if (dep.status !== "active" || dep.variant !== prereq.variant) {
        const blocked = { status: "blocked", variant: null, source: null, blockedBy: `prerequisite:${prereq.model}` };
        memo.set(key, blocked);
        stack.delete(key);
        return blocked;
      }
    }
    const subjectRecord = subjects.get(subjectId) || { id: subjectId, attrs: {} };
    const selected = selectVariant(release, subjectId, subjectRecord, at);
    const result = selected.variant === null
      ? { status: "missing", variant: null, source: null, blockedBy: null }
      : { status: "active", variant: selected.variant, source: selected.source, blockedBy: null };
    memo.set(key, result);
    stack.delete(key);
    return result;
  }

  return {
    assignments: asArray(input.queries).map((query) => {
      const subjectRecord = subjects.get(query.subject) || { id: query.subject };
      const subject = subjectRecord.id;
      const result = evalOne(query.model, subject, query.at);
      return { id: query.id, subject, model: query.model, ...result };
    }),
  };
}

module.exports = { evaluateReleases };
