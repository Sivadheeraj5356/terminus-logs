export function canonJson(value) {
  if (value === null || typeof value !== 'object') {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return `[${value.map((item) => canonJson(item)).join(',')}]`;
  }
  const keys = Object.keys(value).sort();
  const parts = keys.map((key) => `${JSON.stringify(key)}:${canonJson(value[key])}`);
  return `{${parts.join(',')}}`;
}
