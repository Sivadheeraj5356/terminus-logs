const CANONICAL_UTC = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/;

export function normalizeTimestamp(value) {
  if (!CANONICAL_UTC.test(value)) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.valueOf()) || parsed.toISOString() !== value) return null;
  return value;
}

export function addSeconds(value, seconds) {
  return new Date(new Date(value).valueOf() + seconds * 1000).toISOString();
}
