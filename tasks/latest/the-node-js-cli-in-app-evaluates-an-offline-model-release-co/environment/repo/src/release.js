function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function canonicalSubject(subjects, key) {
  for (const subject of asArray(subjects)) {
    if (subject.id === key || asArray(subject.aliases).includes(key)) return subject.id;
  }
  return key;
}

function chooseRelease(releases, model, at) {
  return asArray(releases)
    .filter((item) => item.model === model && item.effective <= at)
    .sort((a, b) => b.effective - a.effective)[0] || null;
}

function evaluateReleases(input) {
  return {
    assignments: asArray(input.queries).map((query) => {
      const subject = canonicalSubject(input.subjects, query.subject);
      const release = chooseRelease(input.releases, query.model, query.at);
      if (!release) return { id: query.id, subject, model: query.model, status: "missing", variant: null, source: null, blockedBy: null };
      const override = asArray(release.overrides).find((item) => item.subject === subject);
      if (override) {
        return { id: query.id, subject, model: query.model, status: "active", variant: override.variant, source: `${release.id}:override:${subject}`, blockedBy: null };
      }
      const variant = release.default || null;
      return { id: query.id, subject, model: query.model, status: variant ? "active" : "missing", variant, source: variant ? `${release.id}:default` : null, blockedBy: null };
    }),
  };
}

module.exports = { evaluateReleases };
