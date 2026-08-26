export interface RowRec {
  instanceUid: string;
  meshId: number;
  classCode: number;
  labels: number[];
  weights: number[];
  o8Score: number;
  latticeLabel: string;
}

export interface TraceCtx {
  profile: number;
}

export interface SegCtx {
  foldUpstream: boolean;
}

export interface BoxCtx {
  cfgPath: string;
}

export interface YamlSink {
  recs: RowRec[];
  push(rec: RowRec): void;
}

export interface D9Cursor {
  stmt: unknown;
  ready: number;
}

export type Database = unknown;
