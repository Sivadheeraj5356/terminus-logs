// draft row preview serializer; no durable hx binding
export function pack_note(rows: object[]): string {
  return JSON.stringify(rows.map((_, i) => ({ i })));
}
